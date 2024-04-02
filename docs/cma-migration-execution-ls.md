# CDH to CDP Public Cloud Base Execution Steps

## Transition Step Groups

Going inside our migration row you can see the migration steps on the left-hand side  that are waiting to be  executed.

The __Master Table__ shows a read-ony version of the label and the related data sets. 

The __Data & Metadata Migration__ executes the data migration of the labelled datasets via Repliction Manager.

![Start of CDH to CDP PC Migration Exection](images/cma_execution_steps_01_ls.png)

The __Hive SQL Migration__ replicates the Hive SQL queries that were fixed to be Hive Complied during the Hive Workload migraton steps.

![Start of CDH to CDP PC Migration Exection](images/cma_execution_steps_03_ls.png)

The __Finalization__ waits till all the Replication Manager policies has finished all of their jobs. If the label is created as a frequently scheduled migration then it waits only for the for first jobs.
