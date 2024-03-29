# SJM
Python script for slurm job monitoring

no other package needed, of course, you are using slurm system with sbatch/sacct tools.



### Usage

```text
usage: SJM [-h] [-p {cpu,fat}] [-m MEM] [-c CPUS_PER_TASK] [-t CHECK_INTERVAL] [-l LINES_PER_TASK] [-gr GIVE_UP_CHECK_ROUND]
                      script [script ...]

To use qsub command more efficiently.

positional arguments:
  script                script file name, mulitple are allowed

optional arguments:
  -h, --help            show this help message and exit
  -p {cpu,fat}, --partition {cpu,fat}
                        --partition for sbatch, default=cpu
  -m MEM, --mem MEM     memory used per task, default=10g
  -c CPUS_PER_TASK, --cpus-per-task CPUS_PER_TASK
                        --cpus-per-task for sbatch, default=1
  -t CHECK_INTERVAL, --interval CHECK_INTERVAL
                        time interval (s) to check your submitted jobs, default=60
  -l LINES_PER_TASK, --lines LINES_PER_TASK
                        split shell scripts by INT lines, default=0, if l==0, do nothing
  -rps, --read_parameters_from_script
						whether to read sbatch parameters from scripts
  -gr GIVE_UP_CHECK_ROUND, --give_up_check_round GIVE_UP_CHECK_ROUND
                        if job still None or Error, it will give up to check your jobs, default=20

There are two modes to run your jobs:
    1. run [INDEPENDENT] jobs by separating jobs with ' ', all jobs will be submitted in the same time.

      e.g.:
        SJM -p cpu -m  100g -c 10 work.sh
        SJM -p fat -m 200g -c 20 -t 200 work.sh [work1.sh work2.sh ]
		SJM -rps -t 100 work.sh   # read sbatch parameters from the header of work.sh
    2. run [SEQUENTIAL] jobs by separating jobs with ",", previous one done and then the following going forward.
       [NOTE]: when you use this mode, you must make sure "#SBATCH "parameters in head of each scrpt,
       while '-c', '-m', and '-p' will become useless.

      e.g.:
        SJM -t 100 step1.sh,step2.sh[,step3.sh]

Author:
yangchentao at genomics.cn
```

