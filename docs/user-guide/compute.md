# Computing Resources Used

## Human GIAB Tutorial

```bash
# Check the resources for a specific node
scontrol show node <node_name>

# Output ---------
NodeName=<node_name> Arch=x86_64 CoresPerSocket=28
    CPUAlloc=56 CPUErr=0 CPUTot=56 CPULoad=0.68
    AvailableFeatures=(null)
    ActiveFeatures=(null)
    Gres=(null)
    NodeAddr=<node_name> NodeHostName=<node_name> Version=17.02
    OS=Linux RealMemory=509577 AllocMem=509577 FreeMem=256579 Sockets=2 Boards=1
    State=ALLOCATED ThreadsPerCore=2 TmpDisk=0 Weight=1 Owner=N/A MCS_label=N/A
    Partitions=<partition_name>,General  
    CfgTRES=cpu=56,mem=509577M
    AllocTRES=cpu=56,mem=509577M
    CapWatts=n/a
    CurrentWatts=0 LowestJoules=0 ConsumedJoules=0
    ExtSensorsJoules=n/s ExtSensorsWatts=0 ExtSensorsTemp=n/s
```
