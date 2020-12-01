####################################################################
## Imports
####################################################################
from __future__ import division
from collections import defaultdict
from Deadline.Events import DeadlineEventListener
from Deadline.Scripting import ClientUtils, RepositoryUtils
from System.Collections.Generic import Dictionary
import json
from math import ceil
import sys
import time

eventPath = RepositoryUtils.GetEventPluginDirectory("Sherpa")

if eventPath not in sys.path:
    sys.path.append(eventPath)

from SherpaUtils import Authenticate, GetResources, ResourceHasOperation, GetResourceTenure, GetSizeTenure, StartResources, StopResources, CreateResources, DeleteResources

TENURE_ONDEMAND = "on-demand"
TENURE_SPOT = "spot"

OPERATION_START = "start"
OPERATION_STOP = "stop"

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
        self.OnSlaveStartingJobCallback += self.OnSlaveStartingJob
        self.OnSlaveRenderingCallback += self.OnSlaveRendering
        self.OnSlaveIdleCallback += self.OnSlaveIdle
        self.OnSlaveStoppedCallback += self.OnSlaveStopped
        self.OnSlaveStalledCallback += self.OnSlaveStalled
        self.OnIdleShutdownCallback += self.OnIdleShutdown
        self.OnMachineStartupCallback += self.OnMachineStartup
        self.OnHouseCleaningCallback += self.OnHouseCleaning
        self.limit_groups = {}
        self.job_targets = {}
        self.plugins = key_arg_defaultdict(plugin_settings)
        self.sherpaClient = None

    def Cleanup(self):
        del self.OnSlaveStartedCallback
        del self.OnSlaveStartingJobCallback
        del self.OnSlaveRenderingCallback
        del self.OnSlaveIdleCallback
        del self.OnSlaveStoppedCallback
        del self.OnSlaveStalledCallback
        del self.OnIdleShutdownCallback
        del self.OnMachineStartupCallback
        del self.OnHouseCleaningCallback

    def OnSlaveStarted(self, slaveName):
        self.register(slaveName)

    def OnSlaveStartingJob(self, slaveName):
        self.register(slaveName)

    def OnSlaveRendering(self, slaveName):
        self.register(slaveName)

    def OnSlaveIdle(self, slaveName):
        self.register(slaveName)

    def OnSlaveStopped(self, slaveName):
        self.register(slaveName)

    def OnSlaveStalled(self, slaveName):
        self.register(slaveName)

    def register(self, slaveName):
        dataFile = self.GetConfigEntryWithDefault("DataFile", "")

        try:
            with open(dataFile) as json_file:
                if self.verLog:
                    self.LogInfo("Reading Sherpa data file: {0}".format(dataFile))

                data = json.load(json_file)

                slaveSettings = RepositoryUtils.GetSlaveSettings(slaveName, True)
                key = self.GetConfigEntryWithDefault("SherpaIdentifierKey", "Sherpa_ID")
                value = slaveSettings.GetSlaveExtraInfoKeyValue(key)

                if not value or value == None:
                    id = data['id']

                    if self.verLog:
                        self.LogInfo("Saving Sherpa ID as extra info key/value pair: {0} (key) + {1} (value)".format(key, id))

                    dict = slaveSettings.SlaveExtraInfoDictionary

                    dict.Add(key, id)

                    slaveSettings.SlaveExtraInfoDictionary = dict
                    RepositoryUtils.SaveSlaveSettings(slaveSettings)

                if self.verLog:
                    self.LogInfo("id: {0}, @type: {1}".format(data['id'], data['@type']))
        except IOError:
            if self.verLog:
                self.LogWarning("Sherpa data file ({0}) could not be read!".format(dataFile))

    def OnMachineStartup(self, groupName, slaveNames, MachineStartupOptions):
        self.GetLogLevel()

        if self.GetBooleanConfigEntryWithDefault("EnablePowerManagement", False) == False:
            if self.verLog:
                self.LogInfo("Sherpa event plugin - power management is not enabled")

            return

        if self.stdLog:
            self.LogInfo("Sherpa event plugin - OnMachineStartup")

        self.handleStartStop(OPERATION_START, slaveNames)

    def OnIdleShutdown(self, groupName, slaveNames, IdleShutdownOptions):
        self.GetLogLevel()

        if self.GetBooleanConfigEntryWithDefault("EnablePowerManagement", False) == False:
            if self.verLog:
                self.LogInfo("Sherpa event plugin - power management is not enabled")

            return

        if self.stdLog:
            self.LogInfo("Sherpa event plugin - OnIdleShutdown")

        self.handleStartStop(OPERATION_STOP, slaveNames)

    def handleStartStop(self, operation, slaveNames):
        self.InitializeSherpaClient()

        for slaveName in slaveNames:
            slaveSettings = RepositoryUtils.GetSlaveSettings(slaveName, True)
            identifierKey = self.GetConfigEntryWithDefault("SherpaIdentifierKey", "Sherpa_ID")
            resourceID = slaveSettings.GetSlaveExtraInfoKeyValue(identifierKey)

            if self.verLog:
                self.LogInfo("Worker's Sherpa ID: {0}".format(resourceID))

            if resourceID:
                if self.stdLog:
                    self.LogInfo("{0} resource: ID {1}.".format(operation.capitalize(), resourceID))

            if resourceID:
                if ResourceHasOperation(
                    self.sherpaClient,
                    resourceID,
                    operation
                ):
                    if self.stdLog:
                        self.LogInfo("{0} resource: ID {1}.".format(operation.capitalize(), resourceID))

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
                else:
                    if self.verLog:
                        self.LogInfo("Resource ({0}) does not have operation ({1}).".format(resourceID, operation))
            else:
                if self.stdLog:
                    self.LogInfo("Resource ID ({0}) not found.".format(resourceID))

    def OnHouseCleaning(self):
        self.GetLogLevel()

        if self.GetBooleanConfigEntryWithDefault("EnableSpotManagement", False) == False:
            if self.verLog:
                self.LogInfo("Sherpa event plugin - spot management is not enabled")

            return

        if self.stdLog:
            self.LogInfo("Sherpa event plugin - OnHouseCleaning")

        self.InitializeSherpaClient()

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
                self.LogWarning("Unable to use Plugin limits for calculating spot targets.")
                self.LogWarning("Please update the Deadline client to match the Deadline Repository version.")

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

        if not projectID or projectID == None:
            raise Exception("Please enter the desired Sherpa project ID.")

        currentNumberOfResources = len(
            GetResources(
                self.sherpaClient,
                projectID
            )
        )

        if self.verLog:
            self.LogInfo("{0} = current number of workers".format(currentNumberOfResources))

        difference = requiredNumberOfWorkers - currentNumberOfResources

        if difference > 0:
            additionalNumberOfResources = min(difference, self.GetIntegerConfigEntryWithDefault("AdditionalNumberOfResourcesPerCycle", 10))

            if self.verLog:
                self.LogInfo("{0} = additional number of resources".format(additionalNumberOfResources))

            projectID = self.GetConfigEntryWithDefault("ProjectID", "")
            prefix = self.GetConfigEntryWithDefault("ResourceName", "DL-SHERPA")
            sizeID = self.GetConfigEntryWithDefault("SizeID", "")
            imageID = self.GetConfigEntryWithDefault("ImageID", "")
            volumeSize = self.GetIntegerConfigEntryWithDefault("VolumeSize", 32)

            if not projectID or projectID == None:
                raise Exception("Please enter the desired Sherpa project ID.")

            if not prefix or prefix == None:
                raise Exception("Please enter the desired resource name.")

            if not sizeID or sizeID == None:
                raise Exception("Please enter the desired Sherpa size ID.")

            tenure = GetSizeTenure(
                self.sherpaClient,
                sizeID
            )

            if self.verLog:
                self.LogInfo("Sherpa size's tenure: {0}".format(tenure))

            if tenure != TENURE_SPOT:
                raise Exception("Please provide a size that has a spot tenure.")

            if not imageID or imageID == None:
                raise Exception("Please enter the desired Sherpa image ID.")

            if not volumeSize or volumeSize == None:
                raise Exception("Please enter the desired resource volume size.")

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

            workerNames = RepositoryUtils.GetSlaveNames(True)

            for workerName in workerNames:
                if self.debugLog:
                    self.LogInfo("{0} = a worker".format(workerName))

                workerInfo = RepositoryUtils.GetSlaveInfo(workerName, True)
                workerState = workerInfo.SlaveState

                if self.debugLog:
                    self.LogInfo("{0} = worker state".format(workerState))

                workerSettings = RepositoryUtils.GetSlaveSettings(workerName, True)

                identifierKey = self.GetConfigEntryWithDefault("SherpaIdentifierKey", "Sherpa_ID")
                resourceID = workerSettings.GetSlaveExtraInfoKeyValue(identifierKey)

                if self.verLog:
                    self.LogInfo("Worker's Sherpa ID: {0}".format(resourceID))

                if resourceID:
                    deleteTimestampKey = self.GetConfigEntryWithDefault("SherpaDeleteTimestampKey", "Sherpa_DeleteTimestamp")
                    coolDownInSeconds = self.GetIntegerConfigEntryWithDefault("CoolDownInSeconds", 300)

                    if workerState == "Idle" or workerState == "Stalled" or workerState == "Offline":
                        deletedKey = self.GetConfigEntryWithDefault("SherpaDeletedKey", "Sherpa_Deleted")
                        deleted = workerSettings.GetSlaveExtraInfoKeyValue(deletedKey)

                        if deleted == "True":
                            return

                        timestamp = workerSettings.GetSlaveExtraInfoKeyValue(deleteTimestampKey)

                        if timestamp:
                            # the worker has already been marked for cooldown
                            now = int(time.time())

                            # is it time to delete the resource?
                            if now > (int(timestamp) + coolDownInSeconds):
                                if self.stdLog:
                                    self.LogInfo("Worker has been {0} for too long (> {1}): {2} > {3} + {1}, request deletion".format(workerState, coolDownInSeconds, now, timestamp))

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
                                self.LogInfo("Sherpa resource's tenure: {0}".format(tenure))

                            if tenure == TENURE_SPOT:
                                # mark worker for cooldown (using timestamp)
                                timestamp = int(time.time())

                                if self.stdLog:
                                    self.LogInfo("Worker is {0}: saving Sherpa delete timestamp as extra info key/value pair: {1} (key) {2} (value)".format(workerState, deleteTimestampKey, timestamp))

                                self.EarmarkForDeletion(workerSettings, timestamp)

    def SetupLimitSettings(self):
        """Creates a dictionary for all Limits containing settings information."""

        limitGroups = RepositoryUtils.GetLimitGroups(True)

        self.limit_groups = {
            limitGroup.Name: LimitSettings(limitGroup)
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
        """For each active job, determine what the target number of resources should be."""

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
        """Returns the active jobs to evaluate."""

        jobs = RepositoryUtils.GetJobsInState("Active")

        if self.verLog:
            self.LogInfo("{0} job(s) in active state".format(len(jobs)))

        for job in sorted(jobs, key=lambda x: x.JobPriority, reverse=True):
            job_has_machine_whitelist = job.JobWhitelistFlag and len(job.JobListedSlaves) > 0

            if (
                not job_has_machine_whitelist
                and not job.IsCorrupted()
            ):
                yield job

    def GetConcurrentTasks(self, job):
        """Returns the number of concurrent tasks for a job. Returns 1 if the plugin disables concurrent tasks."""

        if self.plugins[job.JobPlugin].concurrent_tasks:
            return job.JobConcurrentTasks

        return 1

    def LimitedLimitsForJob(self, job):
        """Returns the distinct Limits for a job and its plugin that are not unlimited."""

        limits = {limit for limit in job.JobLimitGroups}
        limits.union({limit for limit in self.plugins[job.JobPlugin].limits})

        for limitName in limits:
            if self.limit_groups[limitName] is not None and not self.limit_groups[limitName].is_unlimited:
                yield limitName

    def AdjustAvailableStubsForSlave(self, concurrentTasks, num_workers, queuedTasks):
        """Reduces the available stubs for the Limit. Functionality changes depending on the type of the Limit."""

        if self._limitGroup.LimitStubLevel == StubLevel.Task:
            self.availableStubs -= min(concurrentTasks * num_workers, queuedTasks, self.availableStubs)
        else:
            self.availableStubs -= num_workers

    def DetermineWorkerCountForJob(self, job, concurrentTasks):
        """Given a job and the number of concurrentTasks, determine the number of workers that could work on it."""

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
        """Given a job, determine number of queued tasks taking into account the pre-job task behaviour."""

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
                self.LogInfo("{0} = a worker".format(workerName))

            workerInfo = RepositoryUtils.GetSlaveInfo(workerName, True)
            workerState = workerInfo.SlaveState

            if self.verLog:
                self.LogInfo("{0} = worker state".format(workerState))

            if workerState != "Idle" and workerState != "Stalled" and workerState != "Offline":
                deleteTimestampKey = self.GetConfigEntryWithDefault("SherpaDeleteTimestampKey", "Sherpa_DeleteTimestamp")
                workerSettings = RepositoryUtils.GetSlaveSettings(workerName, True)
                existingTimestamp = workerSettings.GetSlaveExtraInfoKeyValue(deleteTimestampKey)

                if existingTimestamp:
                    if self.stdLog:
                        self.LogInfo("Worker is {0}: removing Sherpa delete timestamp as extra info key/value pair: {1} (key)".format(workerState, deleteTimestampKey))

                    self.UnearmarkForDeletion(workerSettings)

    def RemoveDeletedWorkers(self):
        """
        Remove (Offline/Stalled) workers so they do not appear in the Monitor Worker List Panel
        to avoid filling up the list with Workers that will never reconnect.
        """

        if self.GetBooleanConfigEntryWithDefault("RemoveDeletedWorkers", False) == True:
            if self.stdLog:
                self.LogInfo("Remove deleted worker(s)")

            workerNames = RepositoryUtils.GetSlaveNames(True)

            for worker in workerNames:
                workerSettings = RepositoryUtils.GetSlaveSettings(worker, True)

                identifierKey = self.GetConfigEntryWithDefault("SherpaIdentifierKey", "Sherpa_ID")
                resourceID = workerSettings.GetSlaveExtraInfoKeyValue(identifierKey)

                if self.verLog:
                    self.LogInfo("Worker's Sherpa ID: {0}".format(resourceID))

                if resourceID:
                    deletedKey = self.GetConfigEntryWithDefault("SherpaDeletedKey", "Sherpa_Deleted")
                    deleted = workerSettings.GetSlaveExtraInfoKeyValue(deletedKey)

                    if deleted == "True":
                        if self.stdLog:
                            self.LogInfo("Deleted worker: {0}".format(worker))

                        RepositoryUtils.DeleteSlave(worker)

    def EarmarkForDeletion(self, workerSettings, timestamp):
        key = self.GetConfigEntryWithDefault("SherpaDeleteTimestampKey", "Sherpa_DeleteTimestamp")
        value = workerSettings.GetSlaveExtraInfoKeyValue(key)

        if not value or value == None:
            if self.verLog:
                self.LogInfo("Saving delete timestamp as extra info key/value pair: {0} (key) + {1} (value)".format(key, value))

            dict = workerSettings.SlaveExtraInfoDictionary

            dict.Add(key, str(timestamp))

            workerSettings.SlaveExtraInfoDictionary = dict
            RepositoryUtils.SaveSlaveSettings(workerSettings)

    def UnearmarkForDeletion(self, workerSettings):
        key = self.GetConfigEntryWithDefault("SherpaDeleteTimestampKey", "Sherpa_DeleteTimestamp")
        value = workerSettings.GetSlaveExtraInfoKeyValue(key)

        if value != None:
            if self.verLog:
                self.LogInfo("Removing delete timestamp extra info key/value pair: {0} (key) + {1} (value)".format(key, value))

            dict = workerSettings.SlaveExtraInfoDictionary

            dict.Remove(key)

            workerSettings.SlaveExtraInfoDictionary = dict
            RepositoryUtils.SaveSlaveSettings(workerSettings)

    def MarkAsDeleted(self, workerSettings):
        key = self.GetConfigEntryWithDefault("SherpaDeletedKey", "Sherpa_Deleted")
        value = workerSettings.GetSlaveExtraInfoKeyValue(key)

        if not value or value == None:
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
            raise Exception("Please enter your Sherpa API key.")

        if len(secret) <= 0:
            raise Exception("Please enter your Sherpa API secret.")

        if len(endpoint) <= 0:
            raise Exception("Please enter the Sherpa API endpoint.")

        self.sherpaClient = Authenticate(endpoint, key, secret)

class key_arg_defaultdict(defaultdict):
    """A subclass of defaultdict that passes in arguments for missing keys.
    The default factory does not."""

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)

        ret = self[key] = self.default_factory(key)

        return ret

class plugin_settings(object):
    """Stores the concurrent task enabled/disabled information for a plugin."""

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
