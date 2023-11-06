#!/usr/bin/env python3

import subprocess
import time
import sys
import re
import os
import argparse
#from icecream import ic

def match_pattern(text):
    pattern = r'\d+[gGmMkK]+'
    matches = re.findall(pattern, text)
    return matches

def parse_submit_info_get_jobIDs(text):
    job_id = re.match(r'Submitted batch job (\d+)', text).group(1) # get job id')
    return job_id

def parse_job_STATE(text):
    text = text.strip()
    if text == '----------' or text == '':
        return None
    else:
        return text

def update_check_result(thedict, job, state, count):
    if job in thedict:
        thedict[job].update({state: count})
    else:
        thedict.update({job: {state: count}})

def whether_give_up(checked_times, job, sign, give_up_check_round):
    if job in checked_times:
        if sign in checked_times[job]:
            if checked_times[job][sign] > give_up_check_round:
                return True
            else:
                return False
        else:
            return False
    else:
        return False

def check_script_runnable(src):
    sbatch_parameters = {"cpus": 0,
                         "mem": 0,
                         "partition": 0}

    with open(src, 'r') as fh:
        for line in fh.readlines():
            line = line.strip()
            if line.startswith("#SBATCH"):
                if re.search(r' --cpus-per-task=(\d+)', line):
                    sbatch_parameters['cpus'] = re.search(r' --cpus-per-task=(\d+)', line).group(1)
                elif re.search(r' --mem=(\d+)[kKmMgG]', line):
                    sbatch_parameters['mem'] = re.search(r' --mem=(\d+[kKmMgG])', line).group(1)
                elif re.search(r' --partition=(\w+)', line):
                    sbatch_parameters['partition'] = re.search(r' --partition=(\w+)', line).group(1)
            else:
                continue

    if sbatch_parameters["cpus"] and sbatch_parameters["mem"] and sbatch_parameters["partition"]:
        return sbatch_parameters
    else:
        return None


def check_script_header(src):
    with open(src, 'r') as fh:
        text = fh.read()
    if text.startswith("#!/bin/bash") or text.startswith("#!/bin/sh"):
        return True
    else:
        return False


def generate_tasks(scripts, lines=0):
    if lines == 0:
        subscript_dir = os.getcwd()
        return subscript_dir, scripts
    else:
        n_script = 1
        lines_count = 0
        script_tmp = ''
        script_file_basename_list = []
        subscript_dir = str(os.getpid()) + ".submit"
        os.mkdir(subscript_dir)
        for src in scripts:
            countlines_cmd = f"wc -l  {src} | cut -d ' ' -f1"
            cmd_result = subprocess.check_output(countlines_cmd,shell=True)
            total_number = int(cmd_result.decode('utf-8'))
            if total_number <= lines:
                #print(f"the line of {src} is less than split {lines} you set, so do nothing!")
                prefix = src.split("/")[-1].replace(".sh", "")
                basename = f"{prefix}_000001.sh"
                script_file_name = os.path.join(subscript_dir, basename)
                script_file_basename_list.append(basename)
                deal_cmd = f"cp {src} {script_file_name}"
                subprocess.run(deal_cmd, shell=True)
                continue
            if n_script > 99999:
                sys.exit(f"[ERROR]: too many jobs, you got {n_script} jobs!")
            with open(src,'r') as f:
                prefix = src.split("/")[-1].replace(".sh", "")
                if os.path.exists(src) == False:
                    sys.exit(f"Can not find this script or read {src}")
                for line in f.readlines():
                    line = line.strip()
                    if line.startswith("#"):continue
                    script_tmp += f"{line.strip(';')} && echo This-task-completed!\n"
                    lines_count += 1
                    if lines_count==lines:
                        subjob_index = f"{n_script:06d}"  # job number limited to 99999
                        basename = f"{prefix}_{subjob_index}.sh"
                        script_file_name = os.path.join(subscript_dir, basename)
                        script_file_basename_list.append(basename)
                        with open(script_file_name, 'w') as wf:
                            wf.write("#!/bin/sh\n")
                            wf.write(script_tmp)
                        lines_count = 0
                        n_script += 1
                        script_tmp = ''
                if script_tmp:
                    subjob_index = f"{n_script: 6d}"
                    basename = f"{prefix}_{subjob_index}.sh"
                    script_file_name = os.path.join(subscript_dir, basename)
                    script_file_basename_list.append(basename)
                    with open(script_file_name, 'w') as wf:
                        wf.write("#!/bin/sh\n")
                        wf.write(script_tmp)
                else:
                    n_script -= 1
        return subscript_dir, script_file_basename_list

def submit_jobs(scripts, read_parameters_from_script=False,
                lines=0, partition_code="cpu", mem="1g",
                cpus_per_task=1, log=None):
    jobs = {}
    submit_errors = []
    cmd = "/usr/bin/sbatch "
    if read_parameters_from_script == False:
        if match_pattern(mem):
            cmd  = cmd + f" --mem={mem} "
        else:
            sys.exit(f"invlid format of mem {mem}")

        cmd = cmd + f" --partition={partition_code} "
        cmd = cmd + f" --cpus-per-task={cpus_per_task} "

    subscript_dir, splited_scritps = generate_tasks(scripts, lines=lines)
    # move to subdir to submit jobs
    os.chdir(subscript_dir)
    for script in splited_scritps:
        if check_script_header(script) == False:
            sys.exit(f"[ERROR]: script {script} had no hader '#!/bin/bash' or '#!/bin/sh' ")
        if read_parameters_from_script == True:
            submit_parameters = check_script_runnable(script)
            if submit_parameters == None:
                sys.exit(f"in this mode, program need to read parameters from script, but not found or partially lose")
            else:
                mem = submit_parameters["mem"]
                partition = submit_parameters["partition"]
                cpus = submit_parameters["cpus"]

            cmd = f"/usr/bin/sbatch "

        # Submit jobs to the batch system
        sbatch_command = f"{cmd} -o {script}.o  -e {script}.e {script}"
        #process = subprocess.Popen(sbatch_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        #output, error = process.communicate()
        result = subprocess.run(sbatch_command, shell=True, capture_output=True, text=True)
        if result.stderr:
            print("[ERROR]: An error occurred while running the squeue command: {sbatch_command}", result.stderr)
            submit_errors.append(script)
        jobID = parse_submit_info_get_jobIDs(result.stdout)
        jobs[jobID] = script
        print(f"[JOBS]: {jobID} => {script}", file=log)


    if len(submit_errors) > 0:
        print(f"[ERROR]: Some scripts are failed in submitting process: {submit_errors}", file=log)
    return jobs

def monitor_job_status(jobs, interval=60, give_up_check_round=100, log=None):
    jobIDs = jobs.keys()
    total_job = len(jobIDs)
    total_job_set = set(jobs.keys())

    complete_list = set()
    submit_error_list = set()
    check_error_list = set()
    state_error_list = set()
    checking_list = total_job_set - complete_list - check_error_list - state_error_list
    check_round = 0
    checked_times = {}  # record how many times checked for each job;
    job_status = ''
    while checking_list:
        # when len(complete_list) + len(state_error_list) + len(check_error_list) == total_job, stop regually checking
        # Run the sacct command to check the status of the job
        for job in checking_list:
            command = f" /usr/bin/sacct -o State -j {job} | tail -n 3 | head -n 1 "
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            if result.stderr:
                print("[ERROR]: An error occurred while running the squeue command: {command}", result.stderr, file=log)
                submit_error_list.add(job)
                continue

            if check_round == 0:
                # check this job many times in case system may not response immediately
                CHECK_THIS_JOB_TIME_USAGE = 0
                TIME_EXHAUST = 30
                while job_status or CHECK_THIS_JOB_TIME_USAGE > TIME_EXHAUST:
                    # Get the job status from the output
                    job_status = parse_job_STATE(result.stdout)
                    print(job_status)
                    CHECK_THIS_JOB_TIME_USAGE += 5
            else:
                job_status = parse_job_STATE(result.stdout)

            # Print the job status
            print(f"[INFO]: Job ID {job} status: {job_status} in Round {check_round}", file=log)

            # Check if the job has completed
            if job_status == "COMPLETED":
                complete_list.add(job)
            elif job_status in ["RUNNING", "COMPLETING", "PENDING"]:
                1  # do nothing
            elif job_status == None:
                update_check_result(checked_times, job, 'check_error', check_round)
            else:
                # read more -> https://slurm.schedmd.com/squeue.html
                # ['BOOT_FAIL', 'CANCELLED', 'CONFIGURING', 'DEADLINE', 'FAILED', 'NODE_FAIL'， ‘OUT_OF_MEMORY’， ‘PREEMPTED’， ‘RESV_DEL_HOLD’
                # ‘REQUEUE_FED’， ‘REQUEUE_HOLD’， ‘REQUEUED’， ‘RESIZING’， ‘REVOKED’， ‘SIGNALING’， ‘SPECIAL_EXIT’， ‘STAGE_OUT’，‘STOPPED’， ‘SUSPENDED’
                # ‘TIMEOUT’ ]
                # this list is temporary, you need to update it untill all fixed
                update_check_result(checked_times, job, 'state_error', check_round)
            # if after xxx rounds checking, this job'status is still error, I will give up checking
            if whether_give_up(checked_times, job, 'check_error', give_up_check_round) == True:
                check_error_list.add(job)
                print(f"[WARNING]: this job {job} is still with error after {give_up_check_round}, so give up checking", file=log)
            if whether_give_up(checked_times, job, 'state_error', give_up_check_round) == True:
                state_error_list.add(job)
                print(f"[WARNING]: this job {job} is still with error after {give_up_check_round}, so give up checking", file=log)


            checking_list = total_job_set - complete_list - check_error_list - state_error_list - submit_error_list

        # Sleep for the specified interval before checking again
        time.sleep(interval)
        check_round += 1
        log.flush()  # relese cache

    if len(complete_list) == total_job:
        print("[INFO]: All job completed!", file=log)
        return 0
    elif len(submit_error_list) > 0:
        print(f"[ERROR]: Some jobs can not be submitted by sbatch:", file=log)
        for k in list(submit_error_list):
            print(f" {k}\t{jobs[k]}", file=log)
        return 1
    elif len(check_error_list) > 0:
        print(f"[ERROR]: Some jobs can not be checked by sacct:", file=log)
        for k in list(check_error_list):
            print(f" {k}\t{jobs[k]}", file=log)
        return 1
    elif len(state_error_list) > 0:
        print(f"[ERROR]: Some jobs maybe failed according to job STATE:", file=log)
        for k in list(state_error_list):
            print(f" {k}\t{jobs[k]}", file=log)
        return 1


def submit_and_monitor_sequential_jobs(scripts, read_parameters_from_script=True, lines=0, partition_code=None,
                                       mem=None, cpus_per_task=None, check_interval=60,
                                       give_up_check_round=100, log=None):
    job_index = 0
    job_container = {}
    job_finished = {}
    last_job_finished = 1 # assume the last job not finished
    for src in scripts:
        job_index += 1
        job_container[job_index] = src
        if job_index > 1:
            # from the second job, you need check the last job whether finished.
            if job_finished[job_index-1] != 0:
                sys.exit(f"The last job {job_container[job_index-1]} has not finished, check it out")
            else:
                print(f"The last job {job_container[job_index-1]} has finished, now run the next one")
                # Submit jobs to the batch system and return job IDs, jobs is a dict, key=jobID, value=script
                jobs = submit_jobs([src], read_parameters_from_script=True, lines=lines,
                                   partition_code=partition_code, mem=mem,
                                   cpus_per_task=cpus_per_task, log=log)

                # 0 is OK, 1 is not OK
                current_job_finished = monitor_job_status(jobs, interval=check_interval,
                                                  give_up_check_round=give_up_check_round,log=log)
                job_finished[job_index] = current_job_finished
        else:
            # the first job
            jobs = submit_jobs([src], read_parameters_from_script=True, lines=lines,
                               partition_code=partition_code, mem=mem,
                               cpus_per_task=cpus_per_task, log=log)

            # Monitor the job status with a 60-second interval
            current_job_finished = monitor_job_status(jobs, interval=check_interval,
                                                      give_up_check_round=give_up_check_round,log=log)
            job_finished[job_index] = current_job_finished

    # last job status
    last_job_finished = job_finished[job_index]
    return last_job_finished



if __name__ == "__main__":
    description = "To use qsub command more efficiently."

    epilog = f"""
There are two modes to run your jobs:
    1. run [INDEPENDENT] jobs by separating jobs with ' ', all jobs will be submitted in the same time.

      e.g.:
        job_monitor.py -p cpu -m  100g -c 10 work.sh
        job_monitor.py -p fat -m 200g -c 20 -t 200 work.sh [work1.sh work2.sh ]

    2. run [SEQUENTIAL] jobs by separating jobs with ",", previous one done and then the following going forward.
       [NOTE]: when you use this mode, you must make sure "#SBATCH "parameters in head of each scrpt,
       while '-c', '-m', and '-p' will become useless.

      e.g.:
        job_monitor.py -t 100 step1.sh,step2.sh[,step3.sh]

Author:
yangchentao at genomics.cn

"""

    parser = argparse.ArgumentParser(description=description, epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("scripts", metavar="script", nargs="+",
        help="script file name, mulitple are allowed")

    parser.add_argument("-p", "--partition", default="cpu", dest="partition_code",
                        choices=['cpu', 'fat'],
                        help="--partition for sbatch, default=cpu")

    parser.add_argument("-m", "--mem", default="10g", type=str, dest="mem",
                        help="memory used per task, default=10g")

    parser.add_argument("-c", "--cpus-per-task", default=1, type=int, dest="cpus_per_task",
                        help="--cpus-per-task for sbatch, default=1")

    parser.add_argument("-t", "--interval", default=60, type=int, dest="check_interval",
                        help="time interval (s) to check your submitted jobs, default=60")

    parser.add_argument("-l", "--lines", default=0, type=int, dest="lines_per_task",
                        help="split shell scripts by INT lines, default=0, if l==0, do nothing")

    parser.add_argument("-gr", "--give_up_check_round", default=100, type=int, dest="give_up_check_round",
                        help="if job still None or Error, it will give up to check your jobs, default=100")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit()
    else:
        args = parser.parse_args()

    # if jobs separator is ",", run sequentially, if separator is " ", run independently
    run_mode = ''
    pid = str(os.getpid())
    tmp = "".join(args.scripts)
    if "," in tmp:
        run_mode = 'sequential'
        args.scripts = tmp.split(",")
    else:
        run_mode = 'independent'
    # if only one script, log file is named by script subfixed with ".log"; if not, using JOBmonitor.{pid}
    if len(args.scripts) == 1:
        log_file = args.scripts[0] + ".log"
    else:
        log_file = f"JOBmonitor.{pid}.txt"

    log = open(log_file, 'w')
    error = 1
    if run_mode == 'independent':
        # info
        print(f"[INFO]: memory usage: {args.mem}", file=log)
        print(f"[INFO]: cpus-per-task {args.cpus_per_task}", file=log)
        print(f"[INFO]: partition for submit {args.partition_code}", file=log)
        print(f"[INFO]: regularly checking time interval {args.check_interval}s", file=log)
        print("----------------------------------------------------------", file=log)
        # Submit jobs to the batch system and return job IDs, jobs is a dict, key=jobID, value=script
        jobs = submit_jobs(args.scripts, lines=args.lines_per_task,
                        partition_code=args.partition_code, mem=args.mem,
                        cpus_per_task=args.cpus_per_task, log=log)

        # Monitor the job status with a 60-second interval, return 0 if all jobs done
        error = monitor_job_status(jobs,
                        interval=args.check_interval,
                        give_up_check_round=args.give_up_check_round,
                        log=log)

        # the final summary
        print(f"[SUMMARY]-s: =================================================", file=log)
        if error == 0:
            print(f"[INFO]: All done for {jobs}", file=log)
        else:
            print(f"[INFO]: Some jobs are not finished or with error", file=log)
        print(f"[SUMMARY]-e: =================================================", file=log)

    elif run_mode == 'sequential':
            error = submit_and_monitor_sequential_jobs(args.scripts,
                                                   read_parameters_from_script=True,
                                                   check_interval=args.check_interval,
                                                   give_up_check_round=args.give_up_check_round,
                                                   log=log)


    log.close()
