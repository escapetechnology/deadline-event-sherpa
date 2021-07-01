####################################################################
## Imports
####################################################################
from __future__ import division
from collections import defaultdict, OrderedDict
from Deadline.Events import DeadlineEventListener
from Deadline.Scripting import ClientUtils, RepositoryUtils
from System.Collections.Generic import Dictionary
import json
from math import ceil
import platform
import sys
import time

eventPath = RepositoryUtils.GetEventPluginDirectory("Sherpa")

if eventPath not in sys.path:
    sys.path.append(eventPath)

from SherpaUtils import TENURE_ONDEMAND, TENURE_SPOT, OPERATION_START, OPERATION_STOP, MARKING_DELETING, MARKING_DELETED, Authenticate, GetResources, ResourceHasOperation, ResourceHasEnabledOperation, GetResourceTenure, GetResourceMarking, GetResourceSizeID, GetSizeTenure, StartResources, StopResources, CreateResources, DeleteResources

PLUGIN_LIMITS_SUPPORTED = 'GetPluginLimitGroups' in dir(RepositoryUtils)


####################################################################
## This is the function called by Deadline to get an instance of the
## Sherpa event listener.
####################################################################
def GetDeadlineEventListener():
    return SherpaEventListener()


####################################################################
## This is the function called by Deadline when the event plugin is
## no longer in use, so that it can get cleaned up.
####################################################################
def CleanupDeadlineEventListener(deadlinePlugin):
    deadlinePlugin.Cleanup()


###############################################################
## The Sherpa base event listener class.
###############################################################
class SherpaEventListener(DeadlineEventListener):
    def __init__(self):
        self.stdLog = False
        self.verLog = False
        self.debugLog = False
        self.OnSlaveStartedCallback += self.OnSlaveStarted
        self.OnMachineStartupCallback += self.OnMachineStartup
        self.OnIdleShutdownCallback += self.OnIdleShutdown
        self.OnHouseCleaningCallback += self.OnHouseCleaning
        self.limit_groups = {}
        self.job_targets = {}
        self.plugins = key_arg_defaultdict(plugin_settings)
        self.sherpaClient = None

    def Cleanup(self):
        del self.OnSlaveStartedCallback
        del self.OnMachineStartupCallback
        del self.OnIdleShutdownCallback
        del self.OnHouseCleaningCallback

    def OnSlaveStarted(self, slaveName):
        self.GetLogLevel()

        dataFile = None

        if platform.system() == "Linux":
            dataFile = self.GetConfigEntryWithDefault("DataFileLinux", "")

        if platform.system() == "Windows":
            dataFile = self.GetConfigEntryWithDefault("DataFileWindows", "")

        if not dataFile or dataFile is None:
            self.LogWarning("Please enter the desired data file for this OS")
        else:
            if self.verLog:
                self.LogInfo("Using Sherpa data file: {0}".format(dataFile))

        try:
            with open(dataFile) as json_file:
                if self.verLog:
                    self.LogInfo("Reading Sherpa data file: {0}".format(dataFile))

                data = json.load(json_file)

                workerSettings = RepositoryUtils.GetSlaveSettings(workerName, True)
                key = self.GetConfigEntryWithDefault("SherpaIdentifierKey", "Sherpa_ID")
                value = workerSettings.GetSlaveExtraInfoKeyValue(key)

                if not value or value is None:
                    id = data['id']

                    if self.verLog:
                        self.LogInfo("Saving Sherpa ID as extra info key/value pair: {0} (key) + {1} (value)".format(key, id))

                    dict = workerSettings.SlaveExtraInfoDictionary

                    dict.Add(key, id)

                    workerSettings.SlaveExtraInfoDictionary = dict
                    RepositoryUtils.SaveSlaveSettings(workerSettings)

                    # deleting a worker and letting it check in again allows a name change to be picked up
                    # we call out to Sherpa to get the name, not the data file
                    # the latter only gets stamped once and for that reason does not contain the resource name
                    if self.verLog:
                        self.LogInfo("Getting Sherpa resource ({0}) name".format(id))

                    name = GetResourceName(
                        self.sherpaClient,
                        id
                    )

                    if self.verLog:
                        self.LogInfo("Saving Sherpa name as description: {0}".format(name))

                    workerSettings.SlaveDescription = name
                    RepositoryUtils.SaveSlaveSettings(workerSettings)
                if self.verLog:
                    self.LogInfo("id: {0}, @type: {1}".format(data['id'], data['@type']))
        except IOError:
            if self.verLog:
                self.LogWarning("Sherpa data file ({0}) could not be read".format(dataFile))

    def OnMachineStartup(self, groupName, slaveNames, MachineStartupOptions):
        self.GetLogLevel()

        if self.GetBooleanConfigEntryWithDefault("EnablePowerManagement", False) is False:
            if self.verLog:
                self.LogInfo("Sherpa event plugin - power management is not enabled")

            return

        if self.stdLog:
            self.LogInfo("Sherpa event plugin - OnMachineStartup")

        self.handleStartStop(OPERATION_START, slaveNames)

    def OnIdleShutdown(self, groupName, slaveNames, IdleShutdownOptions):
        self.GetLogLevel()

        if self.GetBooleanConfigEntryWithDefault("EnablePowerManagement", False) is False:
            if self.verLog:
                self.LogInfo("Sherpa event plugin - power management is not enabled")

            return

        if self.stdLog:
            self.LogInfo("Sherpa event plugin - OnIdleShutdown")

        self.handleStartStop(OPERATION_STOP, slaveNames)

    def handleStartStop(self, operation, workerNames):
        if len(workerNames) < 1:
            return

        self.InitializeSherpaClient()

        for workerName in workerNames:
            slaveSettings = RepositoryUtils.GetSlaveSettings(workerName, True)
            identifierKey = self.GetConfigEntryWithDefault("SherpaIdentifierKey", "Sherpa_ID")
            resourceID = slaveSettings.GetSlaveExtraInfoKeyValue(identifierKey)

            if self.verLog:
                self.LogInfo("[{0}] Worker's resource ID: {1}".format(workerName, resourceID))

            if resourceID:
                if ResourceHasOperation(
                    self.sherpaClient,
                    resourceID,
                    operation
                ):
                    if self.stdLog:
                        self.LogInfo("[{0}] {1} resource ({2})".format(workerName, operation.capitalize(), resourceID))

                    if ResourceHasEnabledOperation(
                        self.sherpaClient,
                        resourceID,
                        operation
                    ):
                        if operation == OPERATION_START:
                            StartResources(
                                self.sherpaClient,
                                [resourceID]
                            )
                        else:
                            StopResources(
                                self.sherpaClient,
                                [resourceID]
                            )

                        count += 1
                    else:
                        if self.verLog:
                            self.LogInfo("[{0}] Resource ({1}) does not have enabled operation ({2})".format(workerName, resourceID, operation))
                else:
                    if self.verLog:
                        self.LogInfo("[{0}] Resource ({1}) does not have operation ({2})".format(workerName, resourceID, operation))
            else:
                if self.stdLog:
                    self.LogInfo("[{0}] Resource ID not found".format(workerName))

    def OnHouseCleaning(self):
        self.GetLogLevel()

        if self.GetBooleanConfigEntryWithDefault("EnableSpotManagement", False) is False:
            if self.verLog:
                self.LogInfo("Sherpa event plugin - spot management is not enabled")

            return

        if self.stdLog:
            self.LogInfo("Sherpa event plugin - OnHouseCleaning")

        self.InitializeSherpaClient()

        sizeID = self.WorkThroughTheSizeIDs()

        self.RemoveDeletedWorkers()
        self.ResetCooldownTimestamps()
        self.SetupLimitSettings()

        if self.stdLog:
            self.LogInfo("Available Limits:")

            for limit in self.limit_groups:
                if self.limit_groups[limit].is_unlimited:
                    self.LogInfo("\t{0}: Unlimited".format(limit))
                else:
                    self.LogInfo("\t{0}: {1}".format(limit, self.limit_groups[limit].availableStubs))

            if not PLUGIN_LIMITS_SUPPORTED:
                self.LogWarning("Unable to use Plugin limits for calculating spot targets")
                self.LogWarning("Please update the Deadline client to match the Deadline Repository version")

        self.DetermineTargetCapacities()

        requiredNumberOfWorkers = 0

        if self.verLog:
            self.LogInfo("Job targets:")

        for group in self.job_targets:
            for job_id, num_workers in self.job_targets[group].items():
                if self.verLog:
                    self.LogInfo("group: {0} - job: {1}, number of workers: {2}".format(group, job_id, num_workers))

                requiredNumberOfWorkers += num_workers

        if self.verLog:
            self.LogInfo("{0} = required number of workers, PT I".format(requiredNumberOfWorkers))

        requiredNumberOfWorkers = min(requiredNumberOfWorkers, self.GetIntegerConfigEntryWithDefault("MaximumNumberOfResources", 20))

        if self.verLog:
            self.LogInfo("{0} = required number of workers, PT II".format(requiredNumberOfWorkers))

        projectID = self.GetConfigEntryWithDefault("ProjectID", "")

        if not projectID or projectID is None:
            raise Exception("Please enter the desired Sherpa project ID")

        currentNumberOfResources = 0

        resources = GetResources(
            self.sherpaClient,
            projectID
        )

        for resource in resources:
            # we also do not want to include on_demand here, but there's nothing we can do currently other than making GetResourceTenure calls out; which is quite intensive on large scale
            # we do not want to include deleting and deleted resources in the current number of resources, this should be handled by filtering those out in the GetResources above
            if not (resource.marking == MARKING_DELETING or resource.marking == MARKING_DELETED):
                currentNumberOfResources += 1

        if self.verLog:
            self.LogInfo("{0} = current number of resources".format(currentNumberOfResources))

        difference = requiredNumberOfWorkers - currentNumberOfResources

        if difference > 0:
            additionalNumberOfResources = min(difference, self.GetIntegerConfigEntryWithDefault("AdditionalNumberOfResourcesPerCycle", 10))

            if self.verLog:
                self.LogInfo("{0} = additional number of resources".format(additionalNumberOfResources))

            projectID = self.GetConfigEntryWithDefault("ProjectID", "")
            prefix = self.GetConfigEntryWithDefault("ResourceName", "DL-SHERPA")
            imageID = self.GetConfigEntryWithDefault("ImageID", "")
            volumeSize = self.GetIntegerConfigEntryWithDefault("VolumeSize", 32)

            if not projectID or projectID is None:
                raise Exception("Please enter the desired Sherpa project ID")

            if not prefix or prefix is None:
                raise Exception("Please enter the desired resource name")

            if not sizeID or sizeID is None:
                raise Exception("Please enter the desired Sherpa size ID")

            tenure = GetSizeTenure(
                self.sherpaClient,
                sizeID
            )

            if self.verLog:
                self.LogInfo("Sherpa size's tenure: {0}".format(tenure))

            if tenure != TENURE_SPOT:
                raise Exception("Please provide a size that has a spot tenure")

            if not imageID or imageID is None:
                raise Exception("Please enter the desired Sherpa image ID")

            if not volumeSize or volumeSize is None:
                raise Exception("Please enter the desired resource volume size")

            CreateResources(
                self.sherpaClient,
                projectID,
                prefix,
                sizeID,
                imageID,
                volumeSize,
                additionalNumberOfResources
            )
        else:
            excessNumberOfResources = difference

            if self.verLog:
                self.LogInfo("{0} = excess number of worker(s)".format(excessNumberOfResources))

            # clean up resources that checked in as worker(s)
            workerNames = RepositoryUtils.GetSlaveNames(True)

            for workerName in workerNames:
                if self.verLog:
                    self.LogInfo("[{0}] = a worker".format(workerName))

                workerInfo = RepositoryUtils.GetSlaveInfo(workerName, True)
                workerState = workerInfo.SlaveState

                if self.verLog:
                    self.LogInfo("[{0}] {1} = worker state".format(workerName, workerState))

                workerSettings = RepositoryUtils.GetSlaveSettings(workerName, True)

                identifierKey = self.GetConfigEntryWithDefault("SherpaIdentifierKey", "Sherpa_ID")
                resourceID = workerSettings.GetSlaveExtraInfoKeyValue(identifierKey)

                if self.verLog:
                    self.LogInfo("[{0}] Worker's resource ID: {1}".format(workerName, resourceID))

                if resourceID:
                    deleteTimestampKey = self.GetConfigEntryWithDefault("SherpaDeleteTimestampKey", "Sherpa_DeleteTimestamp")
                    coolDownInSeconds = self.GetIntegerConfigEntryWithDefault("CoolDownInSeconds", 300)

                    if workerState == "Idle" or workerState == "Stalled" or workerState == "Offline":
                        deletedKey = self.GetConfigEntryWithDefault("SherpaDeletedKey", "Sherpa_Deleted")
                        deleted = workerSettings.GetSlaveExtraInfoKeyValue(deletedKey)

                        if deleted == "True":
                            continue

                        timestamp = workerSettings.GetSlaveExtraInfoKeyValue(deleteTimestampKey)

                        if timestamp:
                            # the worker has already been marked for cooldown
                            now = int(time.time())

                            # is it time to delete the resource?
                            if now > (int(timestamp) + coolDownInSeconds):
                                if self.stdLog:
                                    self.LogInfo("[{0}] Worker has been {1} for too long (> {2}): {3} > {4} + {2}, request deletion".format(workerName, workerState, coolDownInSeconds, now, timestamp))

                                self.MarkAsDeleted(workerSettings)

                                DeleteResources(
                                    self.sherpaClient,
                                    [resourceID]
                                )
                        else:
                            tenure = GetResourceTenure(
                                self.sherpaClient,
                                resourceID
                            )

                            if self.verLog:
                                self.LogInfo("[{0}] Sherpa resource's tenure: {1}".format(workerName, tenure))

                            if tenure == TENURE_SPOT:
                                # mark worker for cooldown (using timestamp)
                                timestamp = int(time.time())

                                if self.stdLog:
                                    self.LogInfo("[{0}] Worker is {1}: saving Sherpa delete timestamp as extra info key/value pair: {2} (key) {3} (value)".format(workerName, workerState, deleteTimestampKey, timestamp))

                                self.EarmarkForDeletion(workerSettings, timestamp)

            if excessNumberOfResources < 0:
                # clean up "fallback" resources that never checked in as worker(s)
                self.DeleteExcessFallbacksFromResources(resources)

    def SetupLimitSettings(self):
        """Creates a dictionary for all Limits containing settings information"""

        limitGroups = RepositoryUtils.GetLimitGroups(True)

        self.limit_groups = {
            limitGroup.Name: limit_settings(limitGroup)
            for limitGroup in limitGroups
        }

    def GetLogLevel(self):
        logLevel = self.GetConfigEntryWithDefault("Logging", "Standard")

        self.stdLog = self.verLog = False

        if logLevel == "Standard":
            self.stdLog = True
        elif logLevel == "Verbose":
            self.stdLog = self.verLog = True
        elif logLevel == "Debug":
            self.stdLog = self.verLog = self.debugLog = True

    def DetermineTargetCapacities(self):
        """For each active job, determine what the target number of resources should be"""

        self.job_targets = {}

        for job in self.JobsToCheck():
            concurrentTasks = self.GetConcurrentTasks(job)
            num_workers = self.DetermineWorkerCountForJob(job, concurrentTasks)

            # the number of tasks in the rendering state
            if self.verLog:
                self.LogInfo("{0} = number of workers that could work on job".format(num_workers))

            # include the workers that are currently rendering tasks on this job
            num_workers += job.JobRenderingTasks

            # the number of tasks in the rendering state
            if self.verLog:
                self.LogInfo("{0} = currently rendering".format(job.JobRenderingTasks))

            if num_workers:
                if job.Group not in self.job_targets:
                    self.job_targets[job.Group] = {}

                self.job_targets[job.Group][job.JobId] = num_workers

            for limit in self.LimitedLimitsForJob(job):
                self.limit_groups[limit].AdjustAvailableStubsForSlave(concurrentTasks, num_workers, job.JobQueuedTasks)

    def JobsToCheck(self):
        """Returns the active jobs to evaluate"""

        jobs = RepositoryUtils.GetJobsInState("Active")

        if self.verLog:
            self.LogInfo("{0} job(s) in active state".format(len(jobs)))

        for job in sorted(jobs, key=lambda x: x.JobPriority, reverse=True):
            job_has_machine_whitelist = job.JobWhitelistFlag and len(job.JobListedSlaves) > 0

            if (
                not job_has_machine_whitelist and
                not job.IsCorrupted()
            ):
                yield job

    def GetConcurrentTasks(self, job):
        """Returns the number of concurrent tasks for a job. Returns 1 if the plugin disables concurrent tasks"""

        if self.plugins[job.JobPlugin].concurrent_tasks:
            return job.JobConcurrentTasks

        return 1

    def LimitedLimitsForJob(self, job):
        """Returns the distinct Limits for a job and its plugin that are not unlimited"""

        limits = {limit for limit in job.JobLimitGroups}
        limits.union({limit for limit in self.plugins[job.JobPlugin].limits})

        for limitName in limits:
            if self.limit_groups[limitName] is not None and not self.limit_groups[limitName].is_unlimited:
                yield limitName

    def AdjustAvailableStubsForSlave(self, concurrentTasks, num_workers, queuedTasks):
        """Reduces the available stubs for the Limit. Functionality changes depending on the type of the Limit"""

        if self._limitGroup.LimitStubLevel == StubLevel.Task:
            self.availableStubs -= min(concurrentTasks * num_workers, queuedTasks, self.availableStubs)
        else:
            self.availableStubs -= num_workers

    def DetermineWorkerCountForJob(self, job, concurrentTasks):
        """Given a job and the number of concurrentTasks, determine the number of workers that could work on it"""

        queued_tasks = self.GetQueuedTasksForPreJobTaskMode(job)

        # integer division in python 2 returns an int rounded down. To avoid this, we import division from __future__.
        # ceil() returns a float in python 2. The Target of the SFR needs to be an int or long.
        # So, we're converting explicitly to an int.
        num_workers = int(ceil(queued_tasks / concurrentTasks))

        # wxit if num_workers is 0 or negative
        if num_workers <= 0:
            return 0

        for limit in self.LimitedLimitsForJob(job):
            num_workers = min(num_workers, self.limit_groups[limit].MaxSlavesForLimit(concurrentTasks))

            # exit if num_workers is 0 or negative
            if num_workers <= 0:
                return 0

        # apply the Job's Machine Limits to the count of eligible tasks
        machineLimit = RepositoryUtils.GetMachineLimit(job.JobId, True)

        if machineLimit and machineLimit.LimitGroupLimit != 0:
            num_workers = min(num_workers, machineLimit.LimitGroupLimit - machineLimit.LimitInUse)

        if num_workers <= 0:
            return 0

        return num_workers

    def GetQueuedTasksForPreJobTaskMode(self, job):
        """Given a job, determine number of queued tasks taking into account the pre-job task behaviour"""

        queued_tasks = job.JobQueuedTasks

        # check if there is a pre job script and depending on PreJobTaskMode setting,
        # apply certain queued_tasks count behaviour
        if queued_tasks > 1 and job.JobPreJobScript != "":
            pre_job_task_mode = self.GetConfigEntryWithDefault("PreJobTaskMode", "Conservative")

            if pre_job_task_mode == "Normal":
                # if "normal", then treat the pre-job task like a regular job queued task and exit early
                return queued_tasks

            if job.JobCompletedTasks > 0:
                # we have completed tasks; given the nature of pre-job tasks,
                # it should be one of the completed ones
                return queued_tasks

            # no completed tasks yet; means that *only* the pre-job task could be rendered
            if job.JobFailedTasks > 0:
                # we have failed tasks and no completed tasks (should mean the pre-job failed).
                # In this case, no other tasks can be rendered until it is re-queued
                return 0

            if pre_job_task_mode == "Conservative":
                # if "conservative", then treat the queued pre-job task like there is only 1 task to work on
                queued_tasks = 1
            elif pre_job_task_mode == "Ignore":
                # if "ignore", then do not take the pre-job task into account when calculating target capacity
                queued_tasks -= 1

        return queued_tasks

    def ResetCooldownTimestamps(self):
        workerNames = RepositoryUtils.GetSlaveNames(True)

        for workerName in workerNames:
            if self.verLog:
                self.LogInfo("[{0}] = a worker".format(workerName))

            workerInfo = RepositoryUtils.GetSlaveInfo(workerName, True)
            workerState = workerInfo.SlaveState

            if self.verLog:
                self.LogInfo("[{0}] {0} = worker state".format(workerName, workerState))

            if workerState != "Idle" and workerState != "Stalled" and workerState != "Offline":
                deleteTimestampKey = self.GetConfigEntryWithDefault("SherpaDeleteTimestampKey", "Sherpa_DeleteTimestamp")
                workerSettings = RepositoryUtils.GetSlaveSettings(workerName, True)
                existingTimestamp = workerSettings.GetSlaveExtraInfoKeyValue(deleteTimestampKey)

                if existingTimestamp:
                    if self.stdLog:
                        self.LogInfo("[{0}] Worker is {1}: removing Sherpa delete timestamp as extra info key/value pair: {2} (key)".format(workerName, workerState, deleteTimestampKey))

                    self.UnearmarkForDeletion(workerSettings)

    def GetFallbackMarkings(self):
        fallbackMarkings = self.GetConfigEntryWithDefault("SherpaSpotFallbackMarkings", "")
        return [element.strip() for element in fallbackMarkings.split(",")]

    def WorkThroughTheSizeIDs(self):
        sizeID = self.GetConfigEntryWithDefault("SizeID", "")
        sizeIDs = [element.strip() for element in sizeID.split(",")]
        sizeIDs = list(OrderedDict.fromkeys(sizeIDs))  # remove duplicates *whilst keeping the original order*

        if len(sizeIDs) > 1:
            self.LogInfo("Multiple size IDs: {0}".format(sizeIDs))

            needle = self.GetLatestSizeID()

            if needle is None:
                sizeID = sizeIDs[0]

                self.LogInfo("Use the first size ID in the list: {0}".format(sizeID))

                return sizeID
            else:
                # let's "work through the gears"

                self.LogInfo("Last attempted size ID: {0}".format(needle))

                if needle in sizeIDs:
                    if sizeIDs.index(needle) < (len(sizeIDs) - 1):
                        sizeID = sizeIDs[sizeIDs.index(needle) + 1]

                        self.LogInfo("Last attempted size ID was {0}, trying the next one up: {1}".format(needle, sizeID))

                        self.RemoveWorkersWithSizeID(needle)

                        return sizeID
                    else:
                        sizeID = needle

                        self.LogInfo("Last attempted size ID was {0} and that was the last one...".format(sizeID))

                        return sizeID
                else:
                    sizeID = sizeIDs[0]

                    self.LogInfo("Last attempted size ID can not be found in the list, use the first size ID in the list: {0}".format(sizeID))

                    return sizeID
        else:
            sizeID = sizeIDs[0]

            self.LogInfo("Single size ID: {0}".format(sizeID))

            return sizeID

        return None

    def GetLatestSizeID(self):
        projectID = self.GetConfigEntryWithDefault("ProjectID", "")

        if not projectID or projectID is None:
            raise Exception("Please enter the desired Sherpa project ID")

        # @todo implement ability to filter by specific marking(s) *and* size's tenure(s)
        resources = GetResources(
            self.sherpaClient,
            projectID
        )

        fallbackMarkings = self.GetFallbackMarkings()

        for resource in resources:
            needle = resource.marking

            if needle in fallbackMarkings:
                # eg. "no_capacity" could happen to on-demand as well; we want spot only...
                # @todo implement ability to filter by specific marking(s) *and* size's tenure(s) (see above @ GetResources)
                tenure = GetResourceTenure(
                    self.sherpaClient,
                    resource.id
                )

                if self.verLog:
                    self.LogInfo("[{0}] Sherpa resource's tenure: {1}".format(resource.name, tenure))

                if tenure == TENURE_SPOT:
                    return GetResourceSizeID(resource)

        return None

    def RemoveWorkersWithSizeID(self, sizeID):
        self.LogInfo("Remove spot workers with size ID {0}".format(sizeID))

        resourceIDs = []

        projectID = self.GetConfigEntryWithDefault("ProjectID", "")

        if not projectID or projectID is None:
            raise Exception("Please enter the desired Sherpa project ID")

        # @todo implement ability to filter by specific marking(s) *and* size's tenure(s)
        resources = GetResources(
            self.sherpaClient,
            projectID
        )

        fallbackMarkings = self.GetFallbackMarkings()

        for resource in resources:
            needle = resource.marking

            if needle in fallbackMarkings:
                if GetResourceSizeID(resource) == sizeID:
                    # eg. "no_capacity" could happen to on-demand as well; we want spot only...
                    # @todo implement ability to filter by specific marking(s) *and* size's tenure(s) (see above @ GetResources)
                    tenure = GetResourceTenure(
                        self.sherpaClient,
                        resource.id
                    )

                    if self.verLog:
                        self.LogInfo("[{0}] Sherpa resource's tenure: {1}".format(resource.name, tenure))

                    if tenure == TENURE_SPOT:
                        resourceIDs.append(resource.id)

        if len(resourceIDs) > 0:
            # we can just delete these from Sherpa; they never checked in as worker
            # delete resources "en masse" as otherwise the deletion of one resource makes the other resource go back into converging
            DeleteResources(
                self.sherpaClient,
                resourceIDs
            )

    def RemoveDeletedWorkers(self):
        """
        Remove (Offline/Stalled) workers so they do not appear in the Monitor Worker List Panel
        to avoid filling up the list with Workers that will never reconnect.
        """

        if self.GetBooleanConfigEntryWithDefault("RemoveDeletedWorkers", False) is True:
            if self.stdLog:
                self.LogInfo("Remove deleted worker(s)")

            workerNames = RepositoryUtils.GetSlaveNames(True)

            for workerName in workerNames:
                workerSettings = RepositoryUtils.GetSlaveSettings(workerName, True)

                identifierKey = self.GetConfigEntryWithDefault("SherpaIdentifierKey", "Sherpa_ID")
                resourceID = workerSettings.GetSlaveExtraInfoKeyValue(identifierKey)

                if self.verLog:
                    self.LogInfo("[{0}] Worker's resource ID: {0}".format(workerName, resourceID))

                if resourceID:
                    deletedKey = self.GetConfigEntryWithDefault("SherpaDeletedKey", "Sherpa_Deleted")
                    deleted = workerSettings.GetSlaveExtraInfoKeyValue(deletedKey)

                    if deleted == "True":
                        if self.stdLog:
                            self.LogInfo("[{0}] Deleted worker".format(workerName))

                        # if the resource is still around, it will check in again after deletion
                        # let's perform a quick check if the resource has already been destroyed
                        marking = GetResourceMarking(
                            self.sherpaClient,
                            resourceID
                        )

                        if marking == "destroyed":
                            if self.stdLog:
                                self.LogInfo("[{0}] Deleting worker as resource is {1}".format(workerName, marking))

                            RepositoryUtils.DeleteSlave(workerName)
                        else:
                            if self.verLog:
                                self.LogInfo("[{0}] Postpone deletion of worker as resource is {1}".format(workerName, marking))

    def DeleteExcessFallbacksFromResources(self, resources):
        """
        Delete fallback resources, resources that did not get provisioned
        """

        if self.stdLog:
            self.LogInfo("Delete fallback resource(s)")

        fallbackMarkings = self.GetFallbackMarkings()

        resourceIDs = []

        for resource in resources:
            needle = resource.marking

            if needle in fallbackMarkings:
                tenure = GetResourceTenure(
                    self.sherpaClient,
                    resource.id
                )

                if self.verLog:
                    self.LogInfo("[{0}] Sherpa fallback resource: {1}".format(resource.name, needle))

                if tenure == TENURE_SPOT:
                    resourceIDs.append(resource.id)

        if len(resourceIDs) > 0:
            # we can just delete these from Sherpa; they never checked in as worker
            # delete resources "en masse" as otherwise the deletion of one resource makes the other resource go back into converging
            DeleteResources(
                self.sherpaClient,
                resourceIDs
            )

    def EarmarkForDeletion(self, workerSettings, timestamp):
        key = self.GetConfigEntryWithDefault("SherpaDeleteTimestampKey", "Sherpa_DeleteTimestamp")
        value = workerSettings.GetSlaveExtraInfoKeyValue(key)

        if not value or value is None:
            value = str(timestamp)

            if self.verLog:
                self.LogInfo("Saving delete timestamp as extra info key/value pair: {0} (key) + {1} (value)".format(key, value))

            dict = workerSettings.SlaveExtraInfoDictionary

            dict.Add(key, value)

            workerSettings.SlaveExtraInfoDictionary = dict
            RepositoryUtils.SaveSlaveSettings(workerSettings)

    def UnearmarkForDeletion(self, workerSettings):
        key = self.GetConfigEntryWithDefault("SherpaDeleteTimestampKey", "Sherpa_DeleteTimestamp")
        value = workerSettings.GetSlaveExtraInfoKeyValue(key)

        if value is not None:
            if self.verLog:
                self.LogInfo("Removing delete timestamp extra info key/value pair: {0} (key) + {1} (value)".format(key, value))

            dict = workerSettings.SlaveExtraInfoDictionary

            dict.Remove(key)

            workerSettings.SlaveExtraInfoDictionary = dict
            RepositoryUtils.SaveSlaveSettings(workerSettings)

    def MarkAsDeleted(self, workerSettings):
        key = self.GetConfigEntryWithDefault("SherpaDeletedKey", "Sherpa_Deleted")
        value = workerSettings.GetSlaveExtraInfoKeyValue(key)

        if not value or value is None:
            if self.verLog:
                self.LogInfo("Saving deleted as extra info key/value pair: {0} (key) + {1} (value)".format(key, value))

            dict = workerSettings.SlaveExtraInfoDictionary

            dict.Add(key, "True")

            workerSettings.SlaveExtraInfoDictionary = dict
            RepositoryUtils.SaveSlaveSettings(workerSettings)

    def InitializeSherpaClient(self):
        key = self.GetConfigEntryWithDefault("APIKey", "")
        secret = self.GetConfigEntryWithDefault("APISecret", "")
        endpoint = self.GetConfigEntryWithDefault("APIEndpoint", "")

        if len(key) <= 0:
            raise Exception("Please enter your Sherpa API key")

        if len(secret) <= 0:
            raise Exception("Please enter your Sherpa API secret")

        if len(endpoint) <= 0:
            raise Exception("Please enter the Sherpa API endpoint")

        self.sherpaClient = Authenticate(endpoint, key, secret)


class key_arg_defaultdict(defaultdict):
    """A subclass of defaultdict that passes in arguments for missing keys,
    the default factory does not"""

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)

        ret = self[key] = self.default_factory(key)

        return ret


class plugin_settings(object):
    """Stores the concurrent task enabled/disabled information for a plugin"""

    def __init__(self, plugin):
        self.name = plugin
        self.concurrent_tasks = True
        self.initialize_settings()

    def initialize_settings(self):
        """Loads concurrent task information from the Plugin."""

        config = RepositoryUtils.GetPluginConfig(self.name)
        self.concurrent_tasks = config.GetBooleanConfigEntryWithDefault("ConcurrentTasks", True)

        if PLUGIN_LIMITS_SUPPORTED:
            self.limits = RepositoryUtils.GetPluginLimitGroups(self.name)
        else:
            # we don't have scripting API support for this, please update the client
            # replicate previous behavior by pretending the plugin has no assigned limits
            self.limits = []


class limit_settings(object):
    def __init__(self, limitGroup):
        """
        Initializes the limit_settings object.
        Sets available stubs based on whitelist information and number of available Limits.
        """
        self._limitGroup = limitGroup

        if limitGroup.WhitelistFlag and len(limitGroup.LimitGroupListedSlaves) > 0:
            self.availableStubs = 0
        else:
            self.availableStubs = (limitGroup.Limit - limitGroup.LimitInUse) + (
                        limitGroup.LimitGroupOverage - limitGroup.LimitGroupInOverage)

    @property
    def name(self):
        """The name of the Limit Group"""
        return self._limitGroup.LimitGroupName

    @property
    def is_unlimited(self):
        """Returns a boolean based on if the Limit an Unlimited limit."""
        return self._limitGroup.LimitGroupUnlimitedLimit

    def MaxSlavesForLimit(self, concurrentTasks):
        """
        Returns the largest number of Workers that could be started
        based on the available stubs for the Limit and the Limit type.
        """
        if self._limitGroup.LimitStubLevel == StubLevel.Task:
            # integer division in python 2 returns an int rounded down.
            # To avoid this, we want to cast one of the values to a float.
            # ceil() returns a float in python 2. This may effect Target of the SFR, which needs to be an int or long.
            # So, we're converting explicitly to an int.
            return int(ceil(float(self.availableStubs) / concurrentTasks))

        return self.availableStubs

    def AdjustAvailableStubsForSlave(self, concurrentTasks, num_workers, queuedTasks):
        """Reduces the available stubs for the Limit. Functionality changes depending on the type of the Limit."""
        if self._limitGroup.LimitStubLevel == StubLevel.Task:
            self.availableStubs -= min(concurrentTasks * num_workers, queuedTasks, self.availableStubs)
        else:
            self.availableStubs -= num_workers
