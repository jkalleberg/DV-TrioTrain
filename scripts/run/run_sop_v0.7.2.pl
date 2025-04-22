#!/usr/bin/perl 
use lib "/storage/hpc/group/UMAG/CPAN/lib/perl5/";	# Added 11/03/2021 because jobs were failing at slurm submission
use strict;
no strict 'refs';
use autodie;
use Getopt::Long;
use List::MoreUtils qw/ uniq /; 	# Used to get unique libraries
use Cwd;
use Benchmark;
use threads;
use threads::shared;
use Thread::Semaphore;
use Math::NumberCruncher;	
use Time::localtime;
use Proc::Background;
use Email::Sender::Simple qw(sendmail);
use Email::MIME;
use Data::Dumper;
use Sys::Hostname;
use Time::localtime;
use Date::Manip;
use POSIX;

# Tab width set to 2 for optimal reading

# REQUIRED OPTIONS
my $LI = ();									# lab_id of the sample to run
my $TI = ();									# tissue_id of the sample to run
my $InputRef = ();						# Reference genome short name from /REF_GENOME/GENOME.README to use for alignment/variant calling 
my $TaxonID = ();							# NCBI taxon_id for the lab_id to run
my $Analysis = ();						# The type of analysis to run. [wgs,rna,faire,atac]
my $Email = 'nobody';					# Email address to send status updates
my $Lab = 'nobody';						# directory name on /storage/htc/ where to put results
my $SOPVersion = ();					# SOP version of the pipeline passed from CreateSOPrun_vN.N.N.pl

# RUN OPTION DEFAULTS
my $help = ();
my $dups = 0;									# 1 to include duplicate files, 0 to only use unique files
my $dups_dir = "duplicate";		# default 'duplicate' for duplicate files located in duplicate directory, 'base' for duplicate files located in base directory (RNA & FAIRE)
my $DoTrim = 1;								# 1 to do trimmomatic ILLUMINACLIP, 0 to skip, default 1
my $DoAlign = 1;							# 1 to do alignment, 0 to skip, default 1
my $DoMarkDups = 1;						# 1 to do MarkDuplicates, 0 to skip, default 1
my $DoSplitNCigar = 1;				# 1 to do SplitNCigarReads, 0 to skip, default 1.  $Analysis eq 'rna' must also be 1 for this to run
my $DoRealign = 1;						# 1 to do IndelRealignment, 0 to skip, default 1
my $DoCoverage = 1;						# 1 to do DepthOfCoverage, 0 to skip, default 1
my $DoBQSR = 1;								# 1 to do BaseQualityScoreRecalibration, 0 to skip, default 1
my $DoAlignSummary = 1;				# 1 to do AlignmentSummaryMetrics, 0 to skip, default 1
my $DoHC = 1;									# 1 to do HaplotypeCaller, 0 to skip, default 1
my $DoStats = 1;							# 1 to collect system stats, 0 to skip, default 1
my $DoRNA = 0;								# 1 to do RNA-seq analysis, 0 for genomic, [default: 0]
my $Aligner = 'BWA';					# Aligner to use [BWA,STAR,minimap2] default BWA
my $DeleteResults = 1;				# Delete results directory [default: 1]. Used for testing if you do not want the results directory deleted set to 0
my $AdapterFile = 'ADAPTERS.fa';	# Name of adapter file to use for Trimmomatic. Path will be set based on whether running on MUG or Lewis
my $DoIO = 0;									# 1/0 flag to DO [1] or not do [0] IO stats
my $User;											# Grab the user from the environmental variable to determine paths to files
my $UseUnique = 1;						# Switch to use the *Unique.fastq [default 1] or not use the unique [0]. For old data that only has Unique files this should be set to 1 and $DoTrim = 0
my $UnmappedOnly = 0;					# Switch to only do triming/alignment/MarkDups/extract unmapped. Default do entire process [0]
my $CopyResults = 1;					# Copy results to target directory [1 default] [0 do not copy results]. Set to 0 for testing so we don't overwrite real results.
my $bqsrBAQGOP = 40;					# GATK --bqsrBAQGapOpenPenalty [default: 40]. Larger values of 45 or 50 work better for samples divergent from reference.
my $indelQUAL = 45;						# Sets GATK PrintReads parameters --deletions_default_quality and --insertions_default_quality
																# Changing this from the default of 45 does nothing if analysing an existing bam file without the BD and BI tags.
																# These are added by GATK after recalibration.
my $InputQV = 33;							# Input phred quality value
my $StripeCount = 1;					# The Lustre lfs setstripe --stripe-count 
																# Number of OSTs over which to stripe a file. The default value for start_ost is -1 , 
																# which allows the MDS to choose the starting index. A stripe_cnt of 0 uses the file system-wide
																# default stripe count.
my $StripeSize = '1m';				# The Lustre lfs setstripe --stripe-size
																# Number of bytes to store on an OST before moving to the next OST. 
																# A stripe_size of 0 uses the file system's default stripe size, (default is 1 MB).
																# Can be specified with k (KB), m (MB), or g (GB), respectively.
my $BWA_version = 1;					# With BWA2 the indexes are different and we need to point to a different location if using V2
my $UseStarManifest = 0;			# Used with STAR to run all samples at once using a manifest. Added 11/01/2022
																# NOTE: STAR manifest does not work if there are only one set of files in the manifest.
																# It also does not work with a mix of PE and SE reads. The manifest must contain only one type.
my $DoWasp = 0;								# Used with STAR to perform WASP filtering. Added 11/08/2022
my $WaspVCF = ();							# Full path to vcf to use for STAR WASP
my $GTFfile = "/storage/hpc/group/UMAG/REF_GENOME/GFF/9913/1kbulls_ars1.2/Bos_taurus.ARS-UCD1.2.109.gtf";
my $AnnotationVersion = ();		# The integer version of Ensembl annotation GTF to use.
my $DoBam2Cram = 1;						# Convert final alignment files to CRAM 1=CRAM, 0=BAM

# String Variables associated with processing
my $HostName = hostname;			# Server name, used to set a lot of default variables
my $cwd = getcwd;							# 
my $Cpu_Node = 1;							# number of CPU requested on the node
my $Cpu_Trim = 1;							# number of CPU for trimmomatic
my $Cpu_Align = 1;						# number of threads for alignment
my $Cpu_Picard = 1;						# number of CPU for picard
my $Cpu_Samtools = 1;					# number of CPU for samptools
my $Cpu_RTC = 1;							# number of CPU for GATK RealignerTargetCreator
my $Cpu_Realigner = 1;				# number of CPU for GATK IndelRealigner
my $Cpu_SplitNCigar = 1;			# number of CPU for GATK SplitNCigar (This walker cannot use -nt or -nct)
my $Cpu_DOC = 1;							# number of CPU for GATK DepthOfCoverage
my $Cpu_BQSR = 1;							# number of CPU for GATK Realigner
my $Cpu_PR = 1;								# number of CPU for GATK PrintReads
my $Cpu_HC = 1;								# number of CPU for GATK HaplotyeCaller
my $Cpu_ATAC = 1;							# number of CPU for ATAC analysis
my $HT = "OFF";								# Determine whether or not hyperthreading is [ON/OFF] for the system
my $Cpu_Unpaired = 4;					# number of CPU to use for extracting unpaired reads, changed from 1 to 4 04/25/2023
my $Stage;										# The stage name used for sending e-mails when process fails
my $StageNumber = 0;					# The stage number iterator for determining which stage we are in
my $TimeStamp;								# Used to get the timestamp for benchmarking
my $TimeStartAll;							# Timestamp for the overall start of the run
my $TimeStopAll;							# Timestamp for the overall end of the run
my $TimeStart;								# Timestamp for the stage start printed to TIME file
my $TimeEnd;									# Timestamp for the stage end printed to TIME file
my $TimeDiff;									# Difference in $TimeStop - $TimeStart
my $Date;											# Date run started with format 'YYYY-MM-DD'
my $stats;										#
my $stats_pid;								# The PID of the stats collector that is started
my $JavaMem = 4;							# Amount of RAM (GB) to use for java programs. Can be changed for different blocks of code.
my $BqsrSize = 5;							# The size in Mbp to use from each Chr when performing BQSR. [5,10,20] default 5.  Will be set to 10 for everything except WGS. 
my $Pixels = 100;							# Pixel distance to use for MarkDuplicates
my $DirSize = 0;							# Directory size at a given point in the process
my $SortMem = 10;							# Amount of memory to use for Samtool sort
my $MemTotal;									# Total amount of RAM in GB from &Memory # 06/03/2019
my $SortFiles;								# Number of files in ${BAM_PREFIX}_SORT_input.txt that need to be sorted with samtools # 06/03/2019
my $SortMemPerSem;						# GB RAM to be used for each thread in each semaphore for samtools sort # 06/03/2019
my $Library;									# Used to hold the current library being processed from @Unique_Libraries, used for ATAC processing 08/07/2019
my $BWA_ref;									# BWA-MEM2 uses different reference index. If we use $BWA_version == 2 we point to a different location for the index
my $Star;											# Used to set non-standard STAR binaries for testing 04/24/2021
my $NumAlignJobs;							# Number of elements in @FilesForAlign. Used to determine how many threads and semaphores for non-BWA alignment 04/26/2021.
my $semPicardMerge;						# added here 11/04/2022
my $semMarkDups;							# added here 11/04/2022
my $Cpu_FC;										# added here 04/25/2023
my $semFC;										# added here 04/25/2023

# Variables to indicate if a stage is DONE=1 or NOT DONE=0 so we can resume where we left off added 0.6.0 10/18/2020
my $DoneTrim = 0;
my $DoneAlign = 0;
my $DoneSort1 = 0;
my $DonePicardMerge = 0;
my $DoneMarkDups = 	0;
my $DoneMergeDups = 0;
my $DoneIndexDups = 0;
my $DoneUnmapped = 0;
my $DoneSplitNCigar = 0;
my $DoneIndelCreator = 0;
my $DoneIndelRealigner = 0;
my $DoneMergeRealigned = 0;
my $DoneIndexRealigned = 0;
my $DoneBQSR = 0;
my $DoneBQSRreports = 0;
my $DoneMergeRecalibrated = 0;
my $DoneIndexRecalibrated = 0;
my $DoneCoverage = 0;
my $DoneMetrics = 0;
my $DoneHC = 0;
my $DoneAtacStats = 0;
my $DoneWasp = 0;
my $DoneFeatureCounts = 0;
my $DoneBam2Cram = 0;				# Added 04/23/2024
my $DoneCopyFiles = 0;

# String variables associated with animals or files
my $ref;										# Reference file name without [fa] extension
my $TI;											# Tissue_id for the tissue to run
my $BAM_PREFIX;							# The BAM_PREFIX = ${LI}_${TI} is used for tissue specific analysis so that we can create BAM files for each tissue. 
my $BAM_SUFFIX;							# The BAM_SUFFIX is used depending on stage of the process such as [realigned],[realigned.recalibrated] etc.
my $Heterozygosity = 0.001;		# GATK --heterozygosity value [default: 0.001].  Increased to 0.0015 for Taurus and 0.0033 for Indicus.
my $dictionary;							#
my $animal_id;							# ICAR id read from [lab_id]_files.txt as part of @libs
my $lab_id;									# lab_id read from [lab_id]_files.txt as part of @libs
my $tissue_id;							# tissue_id read from [lab_id]_files.txt as part of @libs
my $abbrev;									# 
my $abbrev1;								#
my $abbrev2;								#
my $insert_size;						#
my $insert_stdev;						#
my $forward;								#
my $reverse;								#
my $fordup;									#
my $revdup;									#
my $input_path;							#
my $base_file;							#
my $read_format;						#
my $for_file;								#
my $rev_file;								#
my $KnownSites = 'DEFAULT';	# File name to use for BQSR. If DEFAULT then this is specified around lines 338
my $NumLibraries;						# Number of unique libraries present in $LI_files.txt
my $FileSizeF;							# Size in bytes of the forward file
my $FileSizeR;							# Size in bytes of the reverse file
my $TrimOutBaseFile;				# "${base_file}" OR "${base_file}.DUP"
my $lib;										# First character of $masurca_abbrev indicating the library
my $bwa_output;							# BWA output file name 
my $sam_input;							# Input file name used for samtools
my $NumUnmappedContigs;			# Number of unmapped contigs 
my $NumUnmappedChunks = 100;	# Number of unmapped contigs to process with HC at a time.
my $CollectMetricsNumReads = 30000000;	# Number of reads to process for picard CollectMultipleMetrics;
my $QCflag;									# Quality Control flag [default null] to indicate a QC issue [1]
my $BAMFileSize;						# Size of the realigned.bam file used to determine which BQSR intervals to use
my $Instrument;							# Instrument model from input file. Used to determine the pixel distance in picard MarkDuplicates
my $ExitCode;								# Exit code returned from the CheckExit subroutine
my $CODE;										# used to store the __LINE__ for printing when errors occur
my $semHC;
my $MaxPixelDistance;				# Max pixel distance for MarkDups when multiple libraries present and using STAR manifest to process all libraries for a tissue
my $STARoutFileNamePrefix;	# Name to use for the STAR output file name parameter --outFileNamePrefix 	# Added 04/20/2023

# Iterators
my $t;											# Iterator for threading
my $num;										# Iterator for threading
my $uc;											# Iterator for &IndelRealignUnmapped
my $semIndelRealignUnmapped;	# Counter for &IndelRealignUnmapped
my $semPrintReadsUnmapped;	# Counter for &PrintReadsUnmapped
my $u;		 									# Track threads in &IndelRealignUnmapped
my $num1;										# Track threads in &IndelRealignUnmapped
my $rpg;										# String with values to push into @ReadsPerGene 04/26/2021

# Array Variables
my @FilesToCopy;						# Local files to copy to MUG01_N 
my @Files2DelTrim;					# Local files to delete after trimming
my @Files2DelAlign;					# Local files to delete after alignment
my @Files2DelSort;					# Local files to delete after sorting
my @Files2DelMerge;					# Local files to delete after merging
my @Files2DelRealign;				# Local files to delete after realignment
my @Files2DelRecalibrated;	# Local files to delete after recalibration
my @Files2DelMarkDups;			# Local files to delete after MarkDuplicates
my @Files2DelSplitNCigar;		# Local files to delete after SplitNCigar
my @Files2DelRealigner;			# Local files to delete after IndelRealigner
my @Files2DelRecalibrated;	# Local files to delete after BQSR
my @FilesForAlign;					# File info for alignment
my @FilesForAlign2;					# File info for alignment, same as above but we use this array when when $UseStarManifest==1 and we have a single PE file
my @SeqForIndelTarget;			# Array of chromosome names from dict excluding unmapped contigs
my @SeqForIndelTargetX;			# 
my @SeqForIndelTargetUnmapped;	# Array of UNMAPPED chromosome names from dict
my @IndelRealignThreadsUnmapped;# Array for &IndelRealignUnmapped
my @PrintReadsThreadsUnmapped;	# Array for &PrintReadsUnmapped
my @MergeRealignedFiles;		# Names of realigned bam files [INPUT=${BAM_PREFIX}.${_}.realigned.bam] 
my @MergeRealignedRecalibratedFiles;	# Names of realigned recalibrated bam files [INPUT=${BAM_PREFIX}.UNMAPPED.realigned.recalibrated.bam]
my @UnmappedIndelRealignerBams;	# Array for Unmapped contig chunks bam files to merge back into single bam after IndelRealigner
my @libs;										# Full line from the [lab_id]_files.txt input file. This is split into the individual elements of the file.
my @masurca_abbrev;					# All masurca abbreviations (aa,ab,ac,ba,bb,bc, etc.)
my @files;									# The entire line from readin in $LI_files.txt
my @file_check;							# files to check to make sure they are readable
my @libraries;							# All library abbreviations (a,a,b,c,c, etc.)
my @Unuque_libraries;				# All unique single character libraries (a,b,c, etc.)
my @SortString;							# commands to run samtools sort
my @TissueIDs;							# Array that contains all unique tissue_id for a lab_id. Used to generate input file list of bam files for HC on RNAseq, FAIREseq, ATACseq
my @header;									# Array for the header of the CollectMultipleMetrics output
my @fields;									# Array for each line of the CollectMultipleMetrics output
my @QCwarnings;							# Array for the warning message in the e-mail warning sub
my @TrimResults;						# Array for Trimmomatic trim summary results. Each element is the base file
my @UnpairedString;					# Array used to hold the samtools commands to extract unpaired reads
my @ReadsPerGene;						# Array with comma delimited variables needed for &ReadsPerGene subroutine 04/24/2021
my @StarManifestMergeBams;	# Array with the names of the <two> sorted bam files from STAR manifest that need merged 04/20/2023 
my @FC_jobs;								# Array with the commands to run FeatureCounts

# Hashes
my %genomes;								# [short name / full name] key/value from GENOME.README
my %snps;										# [short name / path name] key/value from GENOME.README
my %hash;										# [$abbrev / integer] Create hash to convert alpha masurca abreviations to integer.
my %SizeOfFiles;						# [$file / $FileSizeF]
my %Instruments;						# [$Instrument / $Pixels] Hash to determine which instrument a library was run on for determining pixel distance in MarkDuplicates
my %LibPixels;							# [$lib / $Pixels] Hash of the libraries and Pixel value to use for MarkDuplicates

# PATHS
my $Trimmomatic;						# Path to the trimmomatic program
my $Picard;									# Path to the picard program
my $GATK;										# Path to the GATK jar
my $GATK4;									# Path to the GATK version 4 jar # Added 01/19/2021
my $Gnuplot;								# Path to the gnuplot program
my $BAMdir;									# Directory on MUG01 where lab_id.realigned.recalibrated.bam files are stored
my $GVCFdir;								# Directory on MUG01 where lab_id.g.vcf files are stored
my $RefGenome;							# /path/to/REF_GENOME (no trailing slash)
my $RefSNP;									# /path/to/SNP (no trailing slash)
my $SampleFileDir;					# /path/to/SampleFileInfo
my $snp_dir;								# $snps{$InputRef}
my $CopyPath;								# Path for the target location on MUG01 to copy files to.  Varies depending on taxon_id, and analysis type.
my $bwa;										# Name of the BWA binary. This is set to 'bwa' or 'BWA-MEM2' based on $BWA_version set on command line
my $Samtools;								# Used to specify a non-default path to samtools for testing different versions
my $Pigz;										# Used to specify a non-default path to pigz for testing different versions

my $options = GetOptions (
	'help|?'										=> \$help,
	'lab_id=i'									=> \$LI,
	'tissue_id=i'								=> \$TI,
	'taxon_id=i'								=> \$TaxonID,
	'analysis=s'								=> \$Analysis,
	'dups=i'										=> \$dups,
	'dups_dir=s'								=> \$dups_dir,
	'ref=s'											=> \$InputRef,
	'cpu=i'											=> \$Cpu_Node,
	'trim=i'										=> \$DoTrim,
	'align=i'										=> \$DoAlign,
	'splitncigar=i'							=> \$DoSplitNCigar,
	'markdups=i'								=> \$DoMarkDups,
	'realign=i'									=> \$DoRealign, 
	'coverage=i'								=> \$DoCoverage,
	'bqsr=i'										=> \$DoBQSR, 
	'bqsrsize=s'								=> \$BqsrSize,
	'known_sites=s'							=> \$KnownSites,									# 11/29/2018
	'hc=i'											=> \$DoHC,
	'stats=i'										=> \$DoStats,
	'rna=i'											=> \$DoRNA,
	'chunks=i'									=> \$NumUnmappedChunks,
	'aligner=s'									=> \$Aligner,
	'CollectMetricsNumReads=i'	=> \$CollectMetricsNumReads,
	'DoAlignSummary=i'					=> \$DoAlignSummary,
	'delete_results=i'					=> \$DeleteResults,
	'adapter_file=s'						=> \$AdapterFile,
	'email=s'										=> \$Email,
	'lab=s'											=> \$Lab,
	'use_unique=i'							=> \$UseUnique,
	'version=s'									=> \$SOPVersion,
	'sort_mem=i'								=> \$SortMem,
	'unmapped_only=i'						=> \$UnmappedOnly,					# 06/05/2019
	'copy_results=i'						=> \$CopyResults,						# 08/23/2019
	'het=s'											=> \$Heterozygosity,				# 09/25/2019
	'bqsrBAQGOP=i'							=> \$bqsrBAQGOP,						# 09/25/2019
	'indelqual=i'								=> \$indelQUAL,							# 09/26/2019
	'input_qv=i'								=> \$InputQV,								# 11/05/2019
	'stripe_count=i'						=> \$StripeCount,						# 10/17/2020
	'stripe_size=s'							=> \$StripeSize,						# 10/17/2020
	'bwa_version=i'							=> \$BWA_version,						# 10/18/2020
	'use_star_manifest=i'				=> \$UseStarManifest,				# 11/01/2022
	'do_wasp=i'									=> \$DoWasp,								# 11/08/2022
	'wasp_vcf=s'								=> \$WaspVCF,								# 11/08/2022
	'gtf_file=s' 								=> \$GTFfile, 							# 04/25/2023
	'annotation_version=i'			=> \$AnnotationVersion,			# 04/25/2023
	'do_bam2cram=i'							=> \$DoBam2Cram							# 04/23/2024
);

if ($help) {
print <<HELP;
THIS NEEDS UPDATED
This runs the SOP pipeline consisting of:
 1)  Trimmomatic to trim and filter reads
 2)  bwa to align reads
 3)  samtools to sort sam files and create bam files
 4)  picard to merge individual bams
 5)  samtools to index the merged bam file
 6)  picard to mark duplicates on merged bam
 7)  samtools to index resulting marked dup bam
 8)  GATK RealignerTargetCreator
 9)  GATK IndelRealigner
 10) GATK BQSR
 11) GATK HaplotypeCaller gVCF mode
 12) GATK VQSR (NOT IMPLEMENTED)

*******************
REQUIRED OPTIONS
	--lab_id		lab_id of the sample to run
	--ref			Reference genome short name from /REF_GENOME/GENOME.README to use for alignment/variant calling
	--taxon_id		NCBI taxon_id for the lab_id to run
	--analysis		Analysis type [wgs,rna,faire,atac]

OPTIONAL
	--help			Print this help list
	--rna			1 to do RNA-seq analysis, 0 for genomic [default: 0]
	--tissue_id		Tissue_id for the tissue to run [default: null]
	--dups			1 to include duplicate files, 0 to only use unique files [default: 0]
	--dups_dir		'duplicate' for duplicate files located in duplicate directory [default: duplicate]
					'base' for duplicate files located in base directory (RNA & FAIRE)
	--cpu			Number of CPU requested
	--trim			1 to do trimmomatic, 0 to skip, [default: 1]
	--align			1 to do alignment, 0 to skip, [default: 1]
	--markdups		1 to do MarkDuplicates, 0 to skip, [default: 1]
	--realign		1 to do IndelRealignment, 0 to skip, [default: 1]
	--coverage		1 to do DepthOfCoverage, 0 to skip, [default: 1]
	--bqsr			1 to do BaseQualityScoreRecalibration, 0 to skip, [default: 1]
	--hc			1 to do HaplotypeCaller, 0 to skip, [default: 1]
	--copy_bam		1 to copy previously generate lab_id.realigned.recalibrated.bam from MUG01 to local, 0 to skip, [default: 0]
	--stats			1 to collect system stats, 0 to skip, [default: 1]
	--drive			SSD,NVME,SCRATCH Passed to system_stats.pl to designate the storage target of CWD [default:undefined]
	--chunks		Number of unmapped contigs to put into a list file to process with HC[default:100]
*******************
HELP
exit;
}

$User = `echo \$USER`;
chomp $User;
print "Host: $HostName\n";
system ("mkdir ${cwd}/tmp");		# Directory where temporary output files for java programs are directed
# Change the Lustre stripe count on the tmp dir to 1 Added 01/07/2020
# This tmp dir usually contains a lot of small files so they should not be striped
# SEE https://www.nics.tennessee.edu/computing-resources/file-systems/io-lustre-tips
system ("lfs setstripe ${cwd}/tmp -c 1");

&HyperThread;						# Check to see if hyperthreading is enabled or not

=pod
$Trimmomatic	= "/cluster/spack/opt/spack/linux-centos7-x86_64/gcc-4.8.5/trimmomatic-0.38-wrfpbncixebqd2nhre7lq6tq5dflk4wr/bin/trimmomatic-0.38.jar";
$Trimmomatic	= "/cluster/spack-2021/opt/spack/linux-centos7-x86_64/gcc-9.3.0/trimmomatic-0.39-6ebemx6rmy7uotnn7v7ig54gjjxpa5bv/bin/trimmomatic";
=cut

$GATK			= "/cluster/spack/opt/spack/linux-centos7-x86_64/gcc-4.8.5/gatk-3.8-1-0-gf15c1c3ef-qlqslekqpddmxmnfad2uk6s7zrbtfrza/bin/GenomeAnalysisTK.jar";
$GATK4		= "/storage/hpc/group/UMAG/SCRIPTS/gatk-4.1.9.0/gatk-package-4.1.9.0-local.jar";
#$Picard	= "/cluster/spack/opt/spack/linux-centos7-x86_64/gcc-4.8.5/picard-2.18.9-tjj3h23c5w5nydgojaar52e5ohh3eu6j/bin/picard.jar";
# Changed picard to 2.26.10 03/11/2022
$Picard		= "/cluster/spack-2022/opt/spack/linux-centos7-x86_64/gcc-9.3.0/picard-2.26.10-5l6sbaaot6j7hjqrrybm7pz3twdne727/bin/picard.jar";

$Trimmomatic 	= `which trimmomatic`;
chomp $Trimmomatic;
my $TrimmomaticVersion = `trimmomatic -version`;
chomp $TrimmomaticVersion;
$Trimmomatic 	= "${Trimmomatic}-${TrimmomaticVersion}.jar";

$Star = `which STAR`;
chomp $Star;
print "372 $Star\n";

#$Picard 		= `which picard`;
#chomp $Picard;

$Gnuplot	= "gnuplot";
$Pigz			= "pigz";
$Samtools	= "samtools";
#$Samtools		= "/storage/hpc/group/UMAG/WORKING/schnabelr/samtools-1.9/samtools";	# For testing non-module versions

# With bwa2 RCSS created a symlink so that just 'bwa' would call 'bwa-mem2' when the bwa/bwa-2.1 module is loaded.
# This works in an interactive shell but when run through slurm we were getting the following error
# slurm_script: line 0: unalias: bwa: not found
# and the alias bwa was not calling bwa-mem2 and failing. So we simply change the way bwa is called in our program here
# and nothing else needs to be changed.
if ($BWA_version == 1) { $bwa = "bwa"; } 
elsif ($BWA_version == 2) { $bwa = "bwa-mem2"; } 

$RefGenome		= "/storage/hpc/group/UMAG/REF_GENOME";
$RefSNP			= "/storage/hpc/group/UMAG/SNP";
$SampleFileDir	= "/storage/hpc/group/UMAG/SampleFileInfo";
$DoIO			= 0;	# We do NOT do IO in the stats collector for Lewis hardware

##########
# CHECK INPUT FLAGS
# Grab the paths to reference files from GENOME.README
open GEN, "${RefGenome}/GENOMES.README";
while (<GEN>) {
	next if $_ =~ m/^#|^\n|^\s/;					# Skip comment lines starting with '#'
	chomp $_;
	my($ref_key, $genome, $snp) =  split(/\s/,$_);
	$genomes{$genome} = $ref_key;
	$snps{$genome} = $snp;
}

if (not exists $genomes{$InputRef}) {
	print "\n\nERROR:\n The input reference specified: \"$InputRef\" \n";
	print "	was not recognized as an existing reference.\n";
	print "	Below are the known reference files in ${RefGenome}/\n\n";
	print "ShortName\tLongName\n";
	foreach (keys %genomes) { print "$_\t$genomes{$_}\t$snps{$_}\n"; }
	print "\n See ${RefGenome}/GENOMES.README\n\n";
	$Stage = "The input reference specified: \"$InputRef\" was not recognized as an existing reference.";
	$CODE = __LINE__;
	&emailFAILURE;
	exit;
}
else {
	$ref = $genomes{$InputRef};
	$snp_dir = $snps{$InputRef};
}

##########
# Setup know sites file for BQSR
# If not defined on the command line we use the default files specified here.
# If defined on the command line then we use that file. This must be in the appropriate directory based on $InputRef
if ($KnownSites eq "DEFAULT") {
	if ($InputRef eq "1kbulls") { $KnownSites = "9913_UMD3.1.vcf.gz"; }				#bgzip and tabix vcf on 6/23/16
	elsif ($InputRef eq "GRCm38.p3") { $KnownSites = "10090_GRCm38.p3.vcf.gz"; }
	elsif ($InputRef eq "1kbulls_ars1.2") { $KnownSites = "190923_ALL.sorted.vcf.gz"; }
	elsif ($InputRef eq "1kbulls_ars1.2.MA") { $KnownSites = "190923_ALL.sorted.vcf.gz"; }
	elsif ($InputRef eq "ensembl_ars1.2.95") { $KnownSites = "190923_ALL.sorted.vcf.gz"; }
	elsif ($InputRef eq "ensembl_umd31") { $KnownSites = "9913_UMD3.1.vcf.gz"; }
	elsif ($InputRef eq "ensembl_umd3.1.94") { $KnownSites = "9913_UMD3.1.vcf.gz"; }
	elsif ($InputRef eq "fca80") { $KnownSites = "9685_fca80.vcf.gz"; }
	elsif ($InputRef eq "fca90") { $KnownSites = "9685_fca90.vcf.gz"; }
#	elsif ($InputRef eq "pig11.1") { $KnownSites = "200503_DBsnp_sus_scrofa.sorted.vcf.gz"; }
	elsif ($InputRef eq "pig11.1") { $KnownSites = "200516_pig.filtered.PASS.vcf.gz"; }
	elsif ($InputRef eq "canfam31") { $KnownSites = "UMC_Canis_familiaris.vcf.gz"; }
	elsif ($InputRef eq "canfam4") { $KnownSites = "UMC_canfam4_BQSR_v3.sorted.vcf.gz"; }
	elsif ($InputRef eq "bee3.1") { $KnownSites = "UMC_bee3.1_BQSR_v3.sorted.vcf.gz"; }
}
elsif ($KnownSites eq "OUTGROUP") {
	if ($InputRef eq "1kbulls") { $KnownSites = "NULL"; }
	elsif ($InputRef eq "GRCm38.p3") { $KnownSites = "NULL"; }
	elsif ($InputRef eq "1kbulls_ars1.2") { $KnownSites = "ARS1.2PlusY_BQSR_Outgroup.vcf.gz"; }
	elsif ($InputRef eq "1kbulls_ars1.2.MA") { $KnownSites = "ARS1.2PlusY_BQSR_Outgroup.vcf.gz"; }
	elsif ($InputRef eq "ensembl_ars1.2.95") { $KnownSites = "ARS1.2PlusY_BQSR_Outgroup.vcf.gz"; }
	elsif ($InputRef eq "ensembl_umd31") { $KnownSites = "9913_UMD3.1.vcf.gz"; }
	elsif ($InputRef eq "ensembl_umd3.1.94") { $KnownSites = "9913_UMD3.1.vcf.gz"; }
	elsif ($InputRef eq "canfam31") { $KnownSites = "NULL"; }
	elsif ($InputRef eq "fca80") { $KnownSites = "NULL"; }
	elsif ($InputRef eq "fca90") { $KnownSites = "NULL"; }
	elsif ($InputRef eq "pig11.1") { $KnownSites = "NULL"; }
}

# Check to make sure that the $KnownSites file can be opened
if ($DoBQSR == 1) {
	if (!(-e -f "${RefSNP}/${snp_dir}/${KnownSites}")) {
		print "\nFile not found: ${RefSNP}/${snp_dir}/${KnownSites}\n";
		$Stage = "File not found: ${RefSNP}/${snp_dir}/${KnownSites}";
		&emailFAILURE; exit;
	}
}

##########
# Check to make sure required options are set
if ($Email eq "nobody") {
	print "You must enter an email address with --email\n";
	$Stage = "You must enter an email address with --email";
	&emailFAILURE; exit();
}
if (!$LI) {
	print "You must enter an integer lab_id with --lab_id\n";
	$Stage = "You must enter an integer lab_id with --lab_id";
	&emailFAILURE; exit();
}
if (!$TaxonID) {
	print "You must enter an integer taxon_id with --taxon_id\n";
	$Stage = "You must enter an integer taxon_id with --taxon_id";
	&emailFAILURE; exit();
}
if (!$Analysis) {
	print "You must enter an analysis type --analysis [wgs,rna,faire,atac]\n";
	$Stage = "You must enter an analysis type --analysis [wgs,rna,faire,atac]";
	&emailFAILURE; exit();
}
if ($Lab eq "nobody") {
	print "You must enter an lab name --lab [schnabellab,johnsonlab,spencerlab,deckerlab,lyondlab]\n";
	$Stage = "You must enter an lab name --lab [schnabellab,johnsonlab,spencerlab,deckerlab,lyondlab]";
	&emailFAILURE; exit();
}

$Analysis = lc $Analysis;
if ($Analysis eq 'rna') { $Aligner = 'STAR'; } # Added 03/09/2018
# We can add to this here when we do single cell or single nuclei processing with STARsolo

# Open LOG, TIME, SIZE files
if ($TI > 0) {
	# The BAM_PREFIX is used for tissue specific analysis so that we can create BAM files for each tissue.
	# If a tissue_id is not specified then all of the files for the given lab_id will be used, even if it is RNA or FAIRE
	$BAM_PREFIX = "${LI}_${TI}";
	open LOG, ">${BAM_PREFIX}.command.LOG";
	open TIME, ">${BAM_PREFIX}.TIME";
	open SIZE, ">${BAM_PREFIX}.SIZE";
	if ($UnmappedOnly == 0) {
		push (@FilesToCopy, "${BAM_PREFIX}.command.LOG");
		push (@FilesToCopy, "${BAM_PREFIX}.TIME");
		push (@FilesToCopy, "${BAM_PREFIX}.SIZE");
	}
}
else {
	$BAM_PREFIX = "${LI}";
	open LOG, ">${BAM_PREFIX}.command.LOG";
	open TIME, ">${BAM_PREFIX}.TIME";
	open SIZE, ">${BAM_PREFIX}.SIZE";
	if ($UnmappedOnly == 0) {
		push (@FilesToCopy, "${BAM_PREFIX}.command.LOG");
		push (@FilesToCopy, "${BAM_PREFIX}.TIME");
		push (@FilesToCopy, "${BAM_PREFIX}.SIZE");
	}
}

# Check to see if DONE file exists for each of the stages
# This lets us know what stages we need to do
if (-e -f "DoneTrim")						{ $DoneTrim = 1; }
if (-e -f "DoneAlign")					{ $DoneAlign = 1; }
if (-e -f "DoneSort1")					{ $DoneSort1 = 1; }
if (-e -f "DonePicardMerge")		{ $DonePicardMerge = 1; }
if (-e -f "DoneMarkDups")				{ $DoneMarkDups = 1; }
if (-e -f "DoneMergeDups")			{ $DoneMergeDups = 1; }
if (-e -f "DoneIndexDups")			{ $DoneIndexDups = 1; }
if (-e -f "DoneUnmapped")				{ $DoneUnmapped = 1; }
if (-e -f "DoneSplitNCigar")		{ $DoneSplitNCigar = 1; }
if (-e -f "DoneIndelCreator")		{ $DoneIndelCreator = 1; }
if (-e -f "DoneIndelRealigner")	{ $DoneIndelRealigner = 1; }
if (-e -f "DoneMergeRealigned")	{ $DoneMergeRealigned = 1; }
if (-e -f "DoneIndexRealigned")	{ $DoneIndexRealigned = 1; }
if (-e -f "DoneBQSR")						{ $DoneBQSR = 1; }
if (-e -f "DoneBQSRreports")		{ $DoneBQSRreports = 1; }
if (-e -f "DoneMergeRecalibrated")	{ $DoneMergeRecalibrated = 1; }
if (-e -f "DoneIndexRecalibrated")	{ $DoneIndexRecalibrated = 1; }
if (-e -f "DoneCoverage")				{ $DoneCoverage = 1; }
if (-e -f "DoneMetrics")				{ $DoneMetrics = 1; }
if (-e -f "DoneHC")							{ $DoneHC = 1; }
if (-e -f "DoneAtacStats")			{ $DoneAtacStats = 1; }
if (-e -f "DoneWASP")						{ $DoneWasp = 1; }
if (-e -f "DoneFeatureCounts")	{ $DoneFeatureCounts = 1; }
if (-e -f "DoneBam2Cram")				{ $DoneBam2Cram = 1; }
if (-e -f "DoneCopyFiles")			{ $DoneCopyFiles = 1; }

# Print variables to LOG file
print LOG "\#BEGIN VARIABLES\n";
print LOG "\#lab_id:\t$LI\n";
print LOG "\#tissue_id:\t$TI\n";
print LOG "\#bam_prefix:\t$BAM_PREFIX\n";
print LOG "\#use duplicates:\t$dups\n";
print LOG "\#duplicate directory:\t$dups_dir\n";
print LOG "\#Host:\t$HostName\n";
print LOG "\#num CPU:\t$Cpu_Node\n";
print LOG "\#HyperThreading:\t$HT\n";
print LOG "\#CWD:\t$cwd\n";
#print LOG "\#StripeCount:\t$StripeCount\n";				# Added 10/17/2020, removed 06/03/2021 due to PFL
#print LOG "\#StripeSize:\t$StripeSize\n";				# Added 10/17/2020, removed 06/03/2021 due to PFL
print LOG "\#SOP:\t$SOPVersion\n";
print LOG "\#UnmappedOnly:\t$UnmappedOnly\n";
print LOG "\#NumUnmappedChunks:\t$NumUnmappedChunks\n"; # Added 01/24/2021 v0.6.1

print LOG "\#TaxonID:\t$TaxonID\n";
print LOG "\#Analysis:\t$Analysis\n";
print LOG "\#Reference:\t$InputRef\n";
print LOG "\#KnownSites:\t$KnownSites\n";
print LOG "\#User:\t$User\n";
print LOG "\#Email:\t$Email\n";
print LOG "\#Lab:\t$Lab\n";

print LOG "\#heterozygosity:\t$Heterozygosity\n";
print LOG "\#Reference Directory:\t$RefGenome\n";
print LOG "\#snp directory:\t$RefSNP\n";
print LOG "\#SampleFileDir:\t$SampleFileDir\n";
if ($Aligner eq "bwa") { print LOG "\#BWA:\t$bwa\tversion:$BWA_version\n"; }
elsif ($Aligner eq "STAR") { print LOG "\#aligner:\t$Aligner\n"; }
elsif ($Aligner eq "minimap2") { print LOG "\#aligner:\t$Aligner\n"; }
print LOG "\#Trimmomatic:\t$Trimmomatic\n";
print LOG "\#Picard:\t$Picard\n";
print LOG "\#GATK:\t$GATK\n";
print LOG "\#GATK4:\t$GATK4\n";
print LOG "\#Gnuplot:\t$Gnuplot\n";
print LOG "\#Samtools:\t$Samtools\n";
print LOG "\#Pigz:\t$Pigz\n";

if ($Analysis eq 'rna') {
print LOG "\#GTF:\t$GTFfile \n";
print LOG "\#AnnotationVersion\t$AnnotationVersion \n"; 
}
if ($DoBam2Cram == 1) { print LOG "\#OUTPUT:\tCRAM \n"; }
else { print LOG "\#OUTPUT:\tBAM \n"; }

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# Need to print the versions of software used
# maybe based on the loaded modules?
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

##########
# Create hash to convert alpha masurca abreviations to integer.
# For duplicate reads we replace the second character with the integer value to indicate the file is a "duplicate" file.
# So masurca_abbrev of aa is the first library and a1 is the duplicate files from library a
@hash{("a".."z")} = (0..25);

##########
# Open input file specifying fastq info
# This is the output of SampleFileInfo_vN.N.N.pl which reads the output of the Access db query providing info for all files for all animals

# Check to see if file exists
if (!(-e -f "$SampleFileDir/$Analysis/${LI}_files.txt")) {
	print "\nFile not found: $SampleFileDir/$Analysis/${LI}_files.txt\n";
	$Stage = "File not found: $SampleFileDir/$Analysis/${LI}_files.txt";
	&emailFAILURE; exit;
}
system ("cp $SampleFileDir/$Analysis/${LI}_files.txt .");
push (@FilesToCopy, "${LI}_files.txt");
system ("dos2unix ${LI}_files.txt");

##########
# Read reference file for Instrument names into hash and assign MarkDups pixel distance
open INST, "${RefGenome}/INSTRUMENTS.TXT";
while (<INST>) {
	chomp $_;
	my $Platform;
	my $ReadPrefix;
	my $FlowcellType;
	($Platform,$Instrument,$ReadPrefix,$FlowcellType) = split(/\t/,$_);
	# $FlowcellType is currently either patterned
	$FlowcellType = lc($FlowcellType);
	if ($FlowcellType eq "patterned") { $Pixels = 2500; }
	else { $Pixels = 100; }
	$Instruments{$Instrument} = $Pixels;
}
close INST;
$Pixels = ();

####################
open IN1, "${LI}_files.txt";				# Read input and set up files for processing
my $h1 = (<IN1>);							# Discard header line
# Library file 
# [0]lab_id [1]tissue_id [2]base_file [3]library [4]read_format [5]masurca_abbreviation [6]insert_size [7]insert_stdev
# [8]umc_name[9]raw_data_pathl [10]raw_data_pathm [11]run_folder [12]unique_file [13]application [14]animal_id (for bwa RG)
# [15]instrument Added 02/24/18

INFILE: while (<IN1>) {
	my $line = $_;
	chomp $line;
	@libs = split(/\t/,$line);
	$lab_id = @libs[0];
	$tissue_id = @libs[1];
	if ($lab_id ne $LI) {
		print "lab id in file ${LI}_files.txt is different than input lab_id\n";
		$Stage = "lab id in file ${LI}_files.txt is different than input lab_id";
		&emailFAILURE; exit;
	}
	# We collect all of the tissue_id for a lab_id in an array and then make it unique after reading the file.
	# This @TissueIDs will be used to generate a file that lists all of the tissue specific bam files from RNAseq, FAIREseq, ATACseq
	# to be used for HaplotypeCaller so that we can genotype samples that have multiple tissue specific bams.
	# 03/24/2019 This was breaking HaplotypeCaller because it was expecting to read all of the bam files in this list	
	if ($tissue_id > 0) {
		push (@TissueIDs, $tissue_id);
	}
	# All of the data for a given lab_id are in the same input file. In order to only process a single tissue_id
	# we move to the next line if the current tissue_id != to the input tissue_id.
	# If the input $TI is not set then it uses all of the data 04/20/2016
	if ($TI > 0 and $TI != $tissue_id) { next INFILE; }

	$abbrev = @libs[5];
	push (@masurca_abbrev,$abbrev);
	$base_file = @libs[2];
	$animal_id = @libs[14];
	$read_format = @libs[4];
	
	# Check to make sure that there is an international_id in @libs[14] and exit if it is null
	if ($animal_id eq "") {
		print "lab_id:$LI is missing an international_id for one of the fastq files.\n";
		$Stage = "lab id:$LI in file ${LI}_files.txt is missing an international_id for one of the fastq files";
		&emailFAILURE; exit;
	}
	if ($dups == 1) {
		$abbrev1 = substr $abbrev, 0, 1;
		$abbrev2 = substr $abbrev, 1, 1;
		$abbrev2 =~ s/(.)/$hash{$1}/g;
		$abbrev2 = "${abbrev1}${abbrev2}";
		push (@masurca_abbrev,$abbrev2);
	}
	$insert_size = @libs[6];
	$insert_stdev = @libs[7];
	# Check to see if the insert size and stdev are defined.  For PE data these should always be present
	# but for single read data we will not have these so we need to assign a dummy standard value.
	# 04/25/2021 
	# This is a legacy of needing the insert size for masurca. Since this is not used or hurting anything we'll just leave it in.
	if ($insert_size eq "") {
		$insert_size = 300;
		$insert_stdev = 75;
	}

	##########
	# Setup hash for library/instrument to determine pixel distance to use for MarkDuplicates
	# Because some libraries may have been run on multiple instruments and one may be a normal flowcell
	# and the other a patterend flowcell we need to check if a $Pixel has already been assigned to the library
	# and whether or not the existing $Pixel is smaller than the current. This way for libraries run on normal and patterned flowcells
	# we always use the larger $Pixel for the patterend flowcell to ensure removing optical duplicates.
	$Instrument = @libs[15];
	if ($Instrument eq "") {
		print LOG "#WARNING Instrument not specified for:\t@libs[8]\n";
		$Instrument = "UNKNOWN";
	}
	$lib = substr($abbrev,0,1);
	### Added 0.5.7 08/24/2018 to throw error and exit if a instrument is not present in the instrument file
	if (!( exists $Instruments{$Instrument} )) {
		print LOG "#ERROR Instrument not specified for:\t@libs[8] $Instrument\n";
		$Stage = "lab id:$LI in file ${LI}_files.txt has an Instrument:\"$Instrument\" not specified in the INSTRUMENT.TXT file";
		&emailFAILURE; exit;
	}
	if ( exists $LibPixels{$lib} ) {
		my $tmpCurPixel = $Instruments{$Instrument};
		my $tmpExistingPixel = $LibPixels{$lib};
		if ( $tmpCurPixel > $tmpExistingPixel ) { $LibPixels{$lib} = $tmpCurPixel; }
	}
	else { $LibPixels{$lib} = $Instruments{$Instrument}; }
	##########
	
	$forward = @libs[8];
	$reverse = @libs[8];
	if ($UseUnique == 1) {								# added 04/07/2018 to use the raw fastq
		$forward =~ s/.fastq/_Unique.fastq.gz/;
		$reverse =~ s/1.fastq/2_Unique.fastq.gz/;
		$fordup = $forward;
		$revdup = $reverse;
		$fordup =~ s/Unique/Duplicate/;
		$revdup =~ s/Unique/Duplicate/;
	}
	else {												# added 04/07/2018 to use the raw fastq
		$forward =~ s/.fastq/.fastq.gz/;
		$reverse =~ s/1.fastq/2.fastq.gz/;
		$fordup = $forward;
		$revdup = $reverse;
		$fordup =~ s/Unique/Duplicate/;
		$revdup =~ s/Unique/Duplicate/;
	}
	
	$input_path = "@libs[9]\/@libs[11]\/";
	$input_path =~ s/\\/\//g;

	# NOTE:	for RNAseq, FAIRE, ATAC the duplicates are in the root directory but for genomic DNA the duplicates are in the "duplicate" directory.
	#	We bandage this by setting the $dups_dir.  This should be "base" for RNAseq, FAIRE, ATAC and "duplicate" for WGS
	if($read_format eq "S") {
		push (@files,"$lab_id $animal_id $base_file $read_format $abbrev $insert_size $insert_stdev ${input_path}$forward\n");
		push (@file_check, "${input_path}$forward");
		if ($dups == 1) {
			if ($dups_dir eq "duplicate") {
				push (@files,"$lab_id $animal_id $base_file $read_format $abbrev2 $insert_size $insert_stdev ${input_path}duplicate\/$fordup\n");
				push (@file_check, "${input_path}duplicate\/$fordup");
			}
			else {
				push (@files,"$lab_id $animal_id $base_file $read_format $abbrev2 $insert_size $insert_stdev ${input_path}$fordup\n");
				push (@file_check, "${input_path}$fordup");
			}
		}
	}
	else {
		# Because of the way we pull the largest average gap size per library, the Nextera long mate pair libraries that get
		# split into the 4 parts will have the long mate pair gap for the category "D" fragments which are actually just PE.
		# So we check to see if the library type indicator is "P" for paired end and if the gap size is large we replace it
		# with a "standard" gap size of 400.
		# 04/25/2021 The issue with gap size is legacy from masurca and we don't use it but it's not hurting anything so we leave it.
		if ($read_format eq "P" && $insert_size > 800) {
			$insert_size = 400;
			$insert_stdev = 70;
		}
		push (@files,"$lab_id $animal_id $base_file $read_format $abbrev $insert_size $insert_stdev ${input_path}$forward ${input_path}$reverse\n");
		push (@file_check, "${input_path}$forward");
		push (@file_check, "${input_path}$reverse");
		if ($dups == 1) {
			if ($dups_dir eq "duplicate") {
				push (@files,"$lab_id $animal_id $base_file $read_format $abbrev2 $insert_size $insert_stdev ${input_path}duplicate\/$fordup ${input_path}duplicate\/$revdup\n");
				push (@file_check, "${input_path}duplicate\/$fordup");
				push (@file_check, "${input_path}duplicate\/$revdup");
			}
			else {
				push (@files,"$lab_id $animal_id $base_file $read_format $abbrev2 $insert_size $insert_stdev ${input_path}$fordup ${input_path}$revdup\n");
				push (@file_check, "${input_path}$fordup");
				push (@file_check, "${input_path}$revdup");
			}
		}
	}
}	
close IN1;

# Get unique list of libratries
foreach (@masurca_abbrev) { push (@libraries, substr($_,0,1)); }
print "##### LIBRARIES PRESENT #####\n";
print "@masurca_abbrev\n";
my @Unique_Libraries = uniq @libraries;
$NumLibraries = @Unique_Libraries;

print "##### LIBRARY PIXEL VALUES #####\n";
my @tmp_pixels;
my @tmp_pixelsSizes;
foreach my $key (sort { $a cmp $b } keys %LibPixels) { 
	print "Key: $key\t$LibPixels{$key}\n";
	push (@tmp_pixels,"$key\|$LibPixels{$key}");
	push @tmp_pixelsSizes,$LibPixels{$key};
}

# Find max pixel distance, needed when using STAR manifest and processing all libraries from a tissue Added 11/02/2022
my @tmp_pixelsMax = sort { $b <=> $a } @tmp_pixelsSizes;
$MaxPixelDistance = $tmp_pixelsMax[0];
print LOG "\#OPTICAL_PIXEL_DISTANCE:\t@tmp_pixels\n";
print LOG "\#MAX_OPTICAL_PIXEL_DISTANCE:\t$MaxPixelDistance\n";
print LOG "\#END VARIABLES\n";

# 03/24/2019 This was breaking HaplotypeCaller because it was expecting to read all of the bam files in this list.
# This was structured this way from long ago when we ran alignments on all of the tissues from a sample and then ran HaplotypeCaller separate.
# This no longer seems appropriate because we want to run HC on each tissue if we run these separate.
# Get unique list of tissue_id and print file with list of paths for bam files to be used for HC
open TI, ">${LI}.tissue.bam.list";
@TissueIDs = uniq @TissueIDs;
if ($DoBQSR == 1) { $BAM_SUFFIX = "realigned.recalibrated"; }
else { $BAM_SUFFIX = "realigned"; }
#print TI "$cwd/${LI}_${TI}.${BAM_SUFFIX}.bam\n";
print TI "$cwd/${BAM_PREFIX}.${BAM_SUFFIX}.bam\n";	# Changed 12/29/2023
close TI;

# Test to make sure each input file can be opened
foreach (@file_check) {
	if (!(-e -f "$_")) {
		print "\nFile not found: $_\n";
		$Stage = "File not found: $_";
		&emailFAILURE; exit;
	}
}

###############################################################################
# Read the dictionary file for the genome reference to pull out the chromosomes and unmapped contig names.
# This is used to parellelize the MARK DUPS, RealignerTargetCreator, IndelRealigner, BQSR PrintReads, HaplotypeCaller
# The unmapped contigs are written to file UNMAPPED_contigs.interval_list
# The named chromosomes are put in array 
$dictionary = $ref;
#$dictionary =~ s/.fa/$ref/;
open DICT, "${RefGenome}/${dictionary}.dict";
open UNMAPPED, ">UNMAPPED_contigs.interval_list";
while (<DICT>) {
	next if $_ =~ m/^\@HD/;				# Skip header lines starting with '@HD'
	chomp $_;
	my ($f1, $SQ) = split(/\s/,$_);
	$SQ =~ s/SN://;

	# The 1kbulls reference uses nonstandard nomenclature for the ChrU contigs so we have to treat those separate.
	if ($InputRef eq "1kbulls") {
		if ($SQ =~ m/chr/i) { push (@SeqForIndelTarget, $SQ); }
		else {
			print UNMAPPED "$SQ\n";
			push (@SeqForIndelTargetUnmapped, $SQ);
		}
	}

	# The FCA9.0 reference uses nonstandard nomenclature for chromosomes and unmapped contigs so we have to treat those separate.
	elsif ($InputRef eq "fca90") {
		if ($SQ !~ m/random/i and $SQ !~ m/ctg/i) { push (@SeqForIndelTarget, $SQ); }
		else {
			print UNMAPPED "$SQ\n";
			push (@SeqForIndelTargetUnmapped, $SQ);
		}
	}

	# Added 01/23/2021
	# The Amel_HAv3.1 reference uses nonstandard nomenclature for chromosomes and unmapped contigs so we have to treat those separate.
	# Added 01/10/2022 or $InputRef eq "Amel_HAv3.1.52_hgd_ids" for the STAR transcriptome that used the bee3.1 fasta
	elsif ($InputRef eq "bee3.1" or $InputRef eq "Amel_HAv3.1.52_hgd_ids") {
		if ($SQ !~ m/NW_/i) { push (@SeqForIndelTarget, $SQ); }
		else {
			print UNMAPPED "$SQ\n";
			push (@SeqForIndelTargetUnmapped, $SQ);
		}
	}
	elsif ($SQ =~ m/chr/i or $SQ =~ m/^[0-9]|^X|^Y|^MT/) { push (@SeqForIndelTarget, $SQ); }	# With Ensembl builds the chromosomes are not prefixed with chr or Chr
	else {
		print UNMAPPED "$SQ\n";
		push (@SeqForIndelTargetUnmapped, $SQ);
	}
}
close DICT;
close UNMAPPED;

# Haplotype caller runs very slow when there are a lot of contigs in an interval file.
# Create a series of interval files for the unmapped contigs based on the number of unmapped contigs and the number of requested CPU.
# For the HC jobs on unmapped contigs we break the contig list up into chunks of $NumUnmappedChunks [default 100 contigs per file].
#
# We previously checked to see if the dict file existed but an edge case arose where the file was present but of zero length.
# This meant that the check passed and the process proceeded with trimming and alignment but failed at indel realignment
# because @SeqForIndelTargetUnmapped was null. So we check that here and error out quickly before proceeding with analysis. 08/22/2019
my $NumSeqForIndelTarget = @SeqForIndelTarget;
$NumUnmappedContigs = @SeqForIndelTargetUnmapped;
my $NumUnmappedHClists = ceil($NumUnmappedContigs / $NumUnmappedChunks);

if ($NumSeqForIndelTarget < 1 or $NumUnmappedContigs < 1) {
	print LOG "#ERROR Number of entries in ${RefGenome}/${dictionary}.dict is zero\n";
	print LOG "#ERROR check to make sure file ${RefGenome}/${dictionary}.dict was created properly.\n";
	$Stage = "lab id:$LI check to make sure file ${RefGenome}/${dictionary}.dict was created properly";
	$CODE = __LINE__;
	&emailFAILURE; exit;
}

my $il = 1;
my $x = 0;
my $x2 = $NumUnmappedChunks;
open UML, ">UNMAPPED_contigsMerge.list";		#list of the ${BAM_PREFIX}.UNMAPPED${uc}.g.vcf.gz to merge

while ($il <= $NumUnmappedHClists) {
	print UML "${BAM_PREFIX}.UNMAPPED${il}.g.vcf.gz\n";
	open UIL, ">UNMAPPED_contigs${il}.interval_list";
	while ($x < $x2 and $x < $NumUnmappedContigs) {
		print UIL "@SeqForIndelTargetUnmapped[$x]\n"; 
		$x++;
	}
	close UIL;
	$x2 = $x2 + $NumUnmappedChunks;
	$il++;
}
close UML;

# Since ChrX is a large chromosome we move it to the beginning of the array so that it runs first.
# We move 4 entries from the end of the array in case there is Chr Y and MT and also to put the unmapped contigs first,
# because if there are a large number of unmapped contigs they take a long time to run.
@SeqForIndelTargetX = @SeqForIndelTarget;
push (@SeqForIndelTargetX,"UNMAPPED");	# Add an UNMAPPED entry to the end. This will serve as a flag later to use an UNMAPPED file.
unshift @SeqForIndelTargetX, pop @SeqForIndelTargetX; 
unshift @SeqForIndelTargetX, pop @SeqForIndelTargetX; 
unshift @SeqForIndelTargetX, pop @SeqForIndelTargetX; 
unshift @SeqForIndelTargetX, pop @SeqForIndelTargetX; 

##########
# grab start time for overall process
$TimeStartAll = new Benchmark;
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t0 ALL\t\t\n";

$Date = yyyymmdd();	# This is 'YYYY-MM-DD' and is used for the date field of the gene counts file for db upload.

##########
# Now that everything is initialized start the systemStats_v#.#.#.pl background process.
# This will collect server stats at 5 second intervals until it is killed.
if ($DoIO == 1) {
	$stats = Proc::Background->new("SystemStats_v0.1.0.pl $BAM_PREFIX 5 0 1");
	$stats_pid = $stats->pid;				# Grab the pid of the stats collector and write to a file so we know the pid in case it needs killed.
	print "\nstats_pid: $stats_pid\n";
	system ("echo \'$stats_pid\' >${BAM_PREFIX}.stats_pid");
}
else {
	$stats = Proc::Background->new("SystemStats_v0.1.0.pl $BAM_PREFIX 5 0 0");
	$stats_pid = $stats->pid;
	print "\nstats_pid: $stats_pid\n";
	system ("echo \'$stats_pid\' >${BAM_PREFIX}.stats_pid");
}

##############################################################################
# TRIMMOMATIC
# RawDataFiles contains the information necessary to run Trimmomatic
# Sort input files by size descending so the largest files are processed first.
# This allows the smaller files to finish at the same time or sooner than the large files.

foreach (@files) {
	my $line = $_;
	print "FILE: $_\n";
	chomp $line;
	#[0]lab_id [1]animal_id [2]base_file [3]read_format [4]abbrev [5]insert_size [6]insert_stdev [7]for_file [8]rev_file
	($lab_id, $animal_id, $base_file, $read_format, $abbrev, $insert_size, $insert_stdev, $for_file, $rev_file) = split(/\s/,$line);
	$FileSizeF = `du "$for_file" | cut -f1`;
	chomp $FileSizeF;	
	print "$FileSizeF\t$for_file\n";	
	
	# If the data are single ended then do not check the reverse file and set it to undefined.
	# This was causing single end data to be not used because the logic below was checking for the size of both the F OR R and failing on the R
	# Also added the M or N for the mate-pair and Nextera library types
	# Fixed 02/19/2018
	if ($read_format eq "P" or $read_format eq "M" or $read_format eq "N") { 
		$FileSizeR = `du "$rev_file" | cut -f1`;
		chomp $FileSizeR;	
		print "$FileSizeR\t$rev_file\n";	
	}
	else { $FileSizeR = (); }

	# Check the file size to make sure there are enough reads.
	# Even fastq files with zero reads will have a file size >0 because of gzip compression.
	# If the file size is < 1kb then we don't add it to the file size hash.  This way when we sort the
	# files based on size we will not process anything that doesn't have enough reads.	
	if ($read_format eq "P" or $read_format eq "M" or $read_format eq "N") { 
		if ($FileSizeF < 1024 or $FileSizeR < 1024) {
			print LOG "\# BEGIN WARNING: the following files did not have enough reads to continue processing and will be excluded\n";
			print LOG "\# FileSize: $FileSizeF: $for_file\n";
			print LOG "\# FileSize: $FileSizeR: $rev_file\n";
			print LOG "\# END WARNING\n";
			print "\# WARNING: the following files did not have enough reads to continue processing and will be excluded\n";
			print "\# FileSize: $FileSizeF: $for_file\n";
			print "\# FileSize: $FileSizeR: $rev_file\n";
		}
		else { $SizeOfFiles{$line} = $FileSizeF; }
	}
	if ($read_format eq "S") {
		if ($FileSizeF < 1024) {
			print LOG "\# BEGIN WARNING: the following files did not have enough reads to continue processing and will be excluded\n";
			print LOG "\# FileSize: $FileSizeF: $for_file\n";
			print LOG "\# END WARNING\n";
			print "\# WARNING: the following files did not have enough reads to continue processing and will be excluded\n";
			print "\# FileSize: $FileSizeF: $for_file\n";
		}
		else { $SizeOfFiles{$line} = $FileSizeF; }
	}
}

# Clear the file array to be repopulated in sorted order
@files = ();
# Sort the hash by the file size and push into new file array
foreach my $file (sort { $SizeOfFiles{$b} <=> $SizeOfFiles{$a} } keys %SizeOfFiles) { push (@files, $file); }
open RDF, ">${BAM_PREFIX}_RawDataFiles.txt";
foreach (@files) { print RDF "$_\n"; }
close RDF;

# Trimomatic as of 0.38 doing adapter trimming uses as many threads as you give it so we determine the number of threads now 06/10/2018
my @TrimThreads;							# Array of threads used for multithreaded trimming
my $TrimSem;								# Number of semaphores we can do based on requested CPU
if (int($Cpu_Node / 12) > 1 ) {				# Changed from 16 to 6 to run on lower core count nodes 09/25/2019
	$TrimSem = int($Cpu_Node / 12);			# Chnaged from 6 to 12 04/26/2023
	$Cpu_Trim = 12;
}

# We need to open this file here so that it is available to the subroutines to write the necessary info to do alignment
open BWAI, ">${BAM_PREFIX}_BWA_input.txt";
# STARI is used when --use_star_manifest $UseStarManifest==1 to write a manifest to do all the alignments together 
# We'll write two STAR manifests, one for PE and one for SE files since it requires all files to be the same type. 02/20/2023
open STARIPE, ">${BAM_PREFIX}_STAR_manifestPE.txt";
open STARISE, ">${BAM_PREFIX}_STAR_manifestSE.txt";

my $semTrim = Thread::Semaphore->new($TrimSem);
$StageNumber++;
$TimeStart = new Benchmark;
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber TRIMMOMATIC\tALL FILES\t\t\n";
print LOG "# TRIMMOMATIC\n";
if ($DoneTrim == 1) { print LOG "# TRIMMOMATIC ALREADY DONE\n"; }

foreach (@files) {
	my $line = $_;
	chomp $line;
	#[0]lab_id [1]animal_id [2]base_file [3]$read_format [4]abbrev [5]insert_size [6]insert_stdev [7]for_file [8]rev_file
	($lab_id, $animal_id, $base_file, $read_format, $abbrev, $insert_size, $insert_stdev, $for_file, $rev_file) = split(/\s/,$line);

	$semTrim->down;
	$t = threads->new(\&trim, $_);
	push(@TrimThreads,$t);
	sleep 1;
}

foreach (@TrimThreads) { $num = $_->join; }
$TimeEnd = new Benchmark;
$TimeDiff = timediff($TimeEnd, $TimeStart);
$TimeStamp = timestamp();
&DirectorySize;
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t${StageNumber} TRIMMOMATIC\tALL FILES\t", timestr($TimeDiff), "\n";
system ("echo \"DONE TRIM\" >DoneTrim");

close BWAI;
close STARIPE;
close STARISE;

sub trim {
	# When duplicate files were included in the analysis we need to specify a new "base file" for the trim output
	# because the normal $base_file only applied to the unique files.  So we take the $base_file and add DUP for the duplicate files.
	if ($for_file =~ m/Duplicate/i) { $TrimOutBaseFile = "${base_file}.DUP"; }
	else { $TrimOutBaseFile = ${base_file}; }

	# $DoTrim = 1 means do adapter trimming with trimmomatic.
	# $DoTrim = 0 should be used on any data that was processed through the UMAG adapter trimming pipeline.
	# There appears to be a bug in Trimmomatic ILLUMINACLIP when it encounters a read(s) that only have 1 base (such as comes out of adaptertrim.pl) and errors out
	# So for data that was previously trimmed we only use Trimmomatic to do base quality trimming 

	# 01/02/2020 v0.5.19 The previous setting for adapter trimming were ${AdapterFile}:2:30:10:1:TRUE
	# For X-Ten and NovaSeq data where the reads were entirely adapter they were being missed and ending up in the $LI.MateUnmapped.1.fastq.gz and reverse files.
	# This is because the "Simple" method has a weight of 0.6 for matching bases which means for a 12 nt adapter the max score is 0.6*12=7.2
	# Thus for the simple matching all of the adapter-only reads were failing to be filtered out.
	# changed the "Simple" threshold to 6 and it solved the problem. Implemented in v0.5.20.pl
	if ($read_format ne "S") {
		if ($DoTrim == 1) {
			print "Trimming file $for_file $rev_file \n";
			print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -jar $Trimmomatic PE -phred${InputQV} -threads $Cpu_Trim -summary ${TrimOutBaseFile}.TRIM.SUMMARY $for_file $rev_file ${TrimOutBaseFile}.1.P.fq ${TrimOutBaseFile}.1.U.fq ${TrimOutBaseFile}.2.P.fq ${TrimOutBaseFile}.2.U.fq MINLEN:35 TOPHRED33 ILLUMINACLIP:${RefGenome}/${AdapterFile}:2:30:6:1:TRUE LEADING:20 TRAILING:20 SLIDINGWINDOW:3:15 AVGQUAL:20 MINLEN:35\n";
			$Stage = "Trimmomatic $LI $TI ${TrimOutBaseFile}";
			if ($DoneTrim == 0) {
				system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -jar $Trimmomatic PE -phred${InputQV} -threads $Cpu_Trim -summary ${TrimOutBaseFile}.TRIM.SUMMARY $for_file $rev_file ${TrimOutBaseFile}.1.P.fq ${TrimOutBaseFile}.1.U.fq ${TrimOutBaseFile}.2.P.fq ${TrimOutBaseFile}.2.U.fq MINLEN:35 TOPHRED33 ILLUMINACLIP:${RefGenome}/${AdapterFile}:2:30:6:1:TRUE LEADING:20 TRAILING:20 SLIDINGWINDOW:3:15 AVGQUAL:20 MINLEN:35"); 
				$CODE = __LINE__; &CheckExit;
			}
			print BWAI "$LI $animal_id $read_format $base_file $abbrev ${TrimOutBaseFile}.P.sam ${TrimOutBaseFile}.1.P.fq ${TrimOutBaseFile}.2.P.fq\n";
			print BWAI "$LI $animal_id $read_format $base_file $abbrev ${TrimOutBaseFile}.U1.sam ${TrimOutBaseFile}.1.U.fq\n";
			print BWAI "$LI $animal_id $read_format $base_file $abbrev ${TrimOutBaseFile}.U2.sam ${TrimOutBaseFile}.2.U.fq\n";
=pod
From STAR manual section 3.2
Another option for mapping multiple reads files, especially convenient for a very large number of
files, is to create a file manifest and supply it in --readFilesManifest /path/to/manifest.tsv.
The manifest file should contain 3 tab-separated columns. 
For paired-end reads:
read1-file-name tab read2-file-name tab read-group-line

For single-end reads, the 2nd column should contain the dash -:
read1-file-name tab - tab read-group-line

Spaces, but not tabs are allowed in the file names. 
If read-group-line does not start with ID:, it can only contain one ID field, and ID: will be added to it.
If read-group-line starts with ID:, it can contain several fields separated by tab, 
and all the fields will be copied verbatim into SAM @RG header line.

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
--Using the STAR manifest option requires all the reads to be either PE or SE, you cannot have a mix of both.
--02/18/2023 So we'll just write the PE files to the manifest for now and fix later.
-- Potential fix is to write two manifests, one for only PE and one for only SE.
-- We will then need to add some logic later to run STAR twice, once with a PE manifest and a 2nd time with a SE manifest.
-- Another problem is that the manifest does not work if there is only one line in the manifest.
	- This will be true when there is a single set of input fastq (PE) which after trimming will generate a single PE line in the manifest.
	- We'll need to add some logic so that if this is the case then we WON'T use the manifest to run STAR for these.
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

!!!!!
There was a problem if we just used ID:${base_file} for the RG
because the Paired and then two Unpaired for each file set created three @RG ID that are duplicates and GATK complained.
So what we do is leave the Paired reads as ID:${base_file} and add UF or UR like ID:${base_file}UF which makes all the @RG unique.
This may cause issues downstream with BQSR because there will be very few reads for these @RG
!!!!!

=cut
			print STARIPE "${TrimOutBaseFile}.1.P.fq\t${TrimOutBaseFile}.2.P.fq\tID:${base_file}\tSM:${animal_id}\tLB:${lib}\tPL:ILLUMINA\n";
			print STARISE "${TrimOutBaseFile}.1.U.fq\t-\tID:${base_file}UF\tSM:${animal_id}\tLB:${lib}\tPL:ILLUMINA\n";
			print STARISE "${TrimOutBaseFile}.2.U.fq\t-\tID:${base_file}UR\tSM:${animal_id}\tLB:${lib}\tPL:ILLUMINA\n";

		}
		else {
			print "Trimming file $for_file $rev_file \n";
			print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -jar $Trimmomatic PE -phred${InputQV} -threads $Cpu_Trim -summary ${TrimOutBaseFile}.TRIM.SUMMARY $for_file $rev_file ${TrimOutBaseFile}.1.P.fq ${TrimOutBaseFile}.1.U.fq ${TrimOutBaseFile}.2.P.fq ${TrimOutBaseFile}.2.U.fq TOPHRED33 MINLEN:35 LEADING:20 TRAILING:20 SLIDINGWINDOW:3:15 AVGQUAL:20 MINLEN:35\n";
			$Stage = "Trimmomatic $LI $TI ${TrimOutBaseFile}";
			if ($DoneTrim == 0) {
				system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -jar $Trimmomatic PE -phred${InputQV} -threads $Cpu_Trim -summary ${TrimOutBaseFile}.TRIM.SUMMARY $for_file $rev_file ${TrimOutBaseFile}.1.P.fq ${TrimOutBaseFile}.1.U.fq ${TrimOutBaseFile}.2.P.fq ${TrimOutBaseFile}.2.U.fq TOPHRED33 MINLEN:35 LEADING:20 TRAILING:20 SLIDINGWINDOW:3:15 AVGQUAL:20 MINLEN:35"); 
				$CODE = __LINE__; &CheckExit;
			}
			print BWAI "$LI $animal_id $read_format $base_file $abbrev ${TrimOutBaseFile}.P.sam ${TrimOutBaseFile}.1.P.fq ${TrimOutBaseFile}.2.P.fq\n";
			print BWAI "$LI $animal_id $read_format $base_file $abbrev ${TrimOutBaseFile}.U1.sam ${TrimOutBaseFile}.1.U.fq\n";
			print BWAI "$LI $animal_id $read_format $base_file $abbrev ${TrimOutBaseFile}.U2.sam ${TrimOutBaseFile}.2.U.fq\n";
			print STARIPE "${TrimOutBaseFile}.1.P.fq\t${TrimOutBaseFile}.2.P.fq\tID:${base_file}\tSM:${animal_id}\tLB:${lib}\tPL:ILLUMINA\n";
			print STARISE "${TrimOutBaseFile}.1.U.fq\t-\tID:${base_file}UF\tSM:${animal_id}\tLB:${lib}\tPL:ILLUMINA\n";
			print STARISE "${TrimOutBaseFile}.2.U.fq\t-\tID:${base_file}UR\tSM:${animal_id}\tLB:${lib}\tPL:ILLUMINA\n";
		}
	}	# End PE
	else {
		if ($DoTrim == 1) {
			print "\nTrimming file $for_file \n";
			print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -jar $Trimmomatic SE -phred${InputQV} -threads $Cpu_Trim -summary ${TrimOutBaseFile}.TRIM.SUMMARY $for_file ${TrimOutBaseFile}.1.U.fq MINLEN:35 TOPHRED33 ILLUMINACLIP:${RefGenome}/${AdapterFile}:2:30:6:1:TRUE LEADING:20 TRAILING:20 SLIDINGWINDOW:3:15 AVGQUAL:20 MINLEN:35\n";
			$Stage = "Trimmomatic $LI $TI ${TrimOutBaseFile}";
			if ($DoneTrim == 0) {
				system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -jar $Trimmomatic SE -phred${InputQV} -threads $Cpu_Trim -summary ${TrimOutBaseFile}.TRIM.SUMMARY $for_file ${TrimOutBaseFile}.1.U.fq MINLEN:35 TOPHRED33 ILLUMINACLIP:${RefGenome}/${AdapterFile}:2:30:6:1:TRUE LEADING:20 TRAILING:20 SLIDINGWINDOW:3:15 AVGQUAL:20 MINLEN:35"); 
				$CODE = __LINE__; &CheckExit;
			}
			print BWAI "$LI $animal_id $read_format $base_file $abbrev ${TrimOutBaseFile}.S.sam ${TrimOutBaseFile}.1.U.fq\n";
			print STARISE "${TrimOutBaseFile}.1.U.fq\t-\tID:${base_file}UF\tSM:${animal_id}\tLB:${lib}\tPL:ILLUMINA\n";
		}
		else {
			print "\nTrimming file $for_file \n";
			print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -jar $Trimmomatic SE -phred${InputQV} -threads $Cpu_Trim -summary ${TrimOutBaseFile}.TRIM.SUMMARY $for_file ${TrimOutBaseFile}.1.U.fq MINLEN:35 TOPHRED33 LEADING:20 TRAILING:20 SLIDINGWINDOW:3:15 AVGQUAL:20 MINLEN:35\n";
			$Stage = "Trimmomatic $LI $TI ${TrimOutBaseFile}";
			if ($DoneTrim == 0) {
				system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -jar $Trimmomatic SE -phred${InputQV} -threads $Cpu_Trim -summary ${TrimOutBaseFile}.TRIM.SUMMARY $for_file ${TrimOutBaseFile}.1.U.fq MINLEN:35 TOPHRED33 LEADING:20 TRAILING:20 SLIDINGWINDOW:3:15 AVGQUAL:20 MINLEN:35"); 
				$CODE = __LINE__; &CheckExit;
			}
			print BWAI "$LI $animal_id $read_format $base_file $abbrev ${TrimOutBaseFile}.S.sam ${TrimOutBaseFile}.1.U.fq\n";
			print STARISE "${TrimOutBaseFile}.1.U.fq\t-\tID:${base_file}UF\tSM:${animal_id}\tLB:${lib}\tPL:ILLUMINA\n";
		}
	}
	$semTrim->up;
}

# Read all the Trimmomatic output files and generate a single ${BAM_PREFIX}.TRIM.SUMMARY.csv that can be uploaded to db
system ("ls *.TRIM.SUMMARY >TRIM.SUMMARY.FILES");
my @TrimFiles;								# array of file names
open TF, "<TRIM.SUMMARY.FILES";
while (<TF>) {
	chomp $_;
	push (@TrimFiles,$_);
}
close TF;
open TS, ">${BAM_PREFIX}.TRIM.SUMMARY.csv";
foreach (@TrimFiles) {
	open TF, "<$_";
	my $FileName = $_;
	$FileName =~ s/\.TRIM.SUMMARY//;

# SE reads have the following output lines
# Input Reads: 47911488 Surviving: 47380754 (98.89%) Dropped: 530734 (1.11%)
# Modified 11/24/2020 to properly grad SE data

	my ($IRP, $BSR, $BSP, $FSR, $FSP, $RSR, $RSP, $DR, $DRP);
	while (<TF>) {
		chomp $_;
		my ($key,$value) = split(/\: /,$_);
		if ($key eq "Input Read Pairs") { $IRP = $value; }
		elsif ($key eq "Input Reads") { $IRP = $value; }
		elsif ($key eq "Both Surviving Reads") { $BSR = $value; }
		elsif ($key eq "Both Surviving Read Percent") { $BSP = $value; }
		elsif ($key eq "Forward Only Surviving Reads") { $FSR = $value; }
		elsif ($key eq "Forward Only Surviving Read Percent") { $FSP = $value; }
		elsif ($key eq "Surviving Reads") { $FSR = $value; }
		elsif ($key eq "Surviving Read Percent") { $FSP = $value; }
		elsif ($key eq "Reverse Only Surviving Reads") { $RSR = $value; }
		elsif ($key eq "Reverse Only Surviving Read Percent") { $RSP = $value; }
		elsif ($key eq "Dropped Reads") { $DR = $value; }
		elsif ($key eq "Dropped") { $DR = $value; }
		elsif ($key eq "Dropped Read Percent") { $DRP = $value; }
	}
	close TF;
push (@TrimResults,"$FileName,$IRP,$BSR,$BSP,$FSR,$FSP,$RSR,$RSP,$DR,$DRP");
print TS "$FileName,$IRP,$BSR,$BSP,$FSR,$FSP,$RSR,$RSP,$DR,$DRP\n";
}
close TS;
push (@FilesToCopy,"${BAM_PREFIX}.TRIM.SUMMARY.csv");

###############################################################################
# ALIGN
# BWA_input.txt contains the information necessary to run bwa (also in array @FilesForAlign)
# When we added the $UseStarManifest=1 we just push the single file into the @FilesForAlign array.
# This allows the logic that uses the number of elements in this array to determin semaphores to still work
# since the length will be 1 for the manifest version. Added 11/01/2022

# STAR is not liking a mix of PE and SE files in the manifest
# STAR cannot read a manifest of SE & PE files. If you want to run both they need to be run separate.
# See https://github.com/alexdobin/STAR/issues/1698

#################################################################################
# The BWAI file contains single entries for all fastq files produced by trimming.
# When we are using a STAR manifest and we only have a single entry for anything, we need to match the
# files from the STAR manifest (either STARISE or STARIPE) to the files from the @FilesForAlign2 array
# and process them as if we were not using a manifest. 02/21/2023
 
open BWAI, "<${BAM_PREFIX}_BWA_input.txt";
while (<BWAI>) {
	chomp $_;
	if ($UseStarManifest == 0) {
		push (@FilesForAlign, $_);
	}
	else {
		push (@FilesForAlign2, $_);
	}
}
close BWAI;

# When trimming we write the PE fastq to one manifest and the SE to another.
# We'll push both of these into the FilesForAlign array to process both of them.
if ($UseStarManifest == 1) {
	push (@FilesForAlign, "${BAM_PREFIX}_STAR_manifestPE.txt"); 
	push (@FilesForAlign, "${BAM_PREFIX}_STAR_manifestSE.txt"); 
}
#
#################################################################################

open SORTI, ">${BAM_PREFIX}_SORT_input.txt";

$StageNumber++;
$TimeStart = new Benchmark;
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber ALIGN\tALL FILES\t\t\n";
print LOG "# ALIGN\n";
if ($DoneAlign == 1) { print LOG "# ALIGN ALREADY DONE\n"; }

$NumAlignJobs = @FilesForAlign;					# Added 04/26/2021
#print "1175 NumAlignJobs: $NumAlignJobs\n";
my $AlignSem = 1;
if ($Aligner eq "BWA") {
	$AlignSem = 1;
	$Cpu_Align = $Cpu_Node;						# Changed 09/25/2019 to remove the subtraction of 1 core
}
=pod
04/26/2021 When running STAR we previously just used 6 threads.
This was largely due to a relatively large number of files for each transcriptome with a relatively small number of reads per file.
This situation was spending more time loading the genome index than actually aligning so we spawned more jobs.
However, newer data is mainly one set of files for each transcriptome, in which case we want to use as many threads as possible.

#elsif (int($Cpu_Node / 6) > 1 ) {
#	$AlignSem = int($Cpu_Node / 6);
#	$Cpu_Align = 6;
#}
=cut
elsif ($Cpu_Node > 1 ) {
	if ($UseStarManifest == 0) {
		# Updated STAR logic 04/26/2021
		# For RNAseq there will almost always be a job for paired reads and 2 jobs for the unpaired after trimming.
		# The unpaired files are generally small and don't take much time. If we evenly distribute cores and semaphores
		# based on the number of jobs we will be taking away cores from the larger jobs. If we take the number of jobs
		# and divide by 3 to allocate most of the cores to the large jobs then these will run faster at the expense of
		# having fewer semaphores to run the small jobs simultaneously.
		# Updated STAR logic for $UseStarManifest == 1 02/21/2023
		# With processing the STARIPE and STARISE manifests we will always have at lease two align jobs
		my $tmp_jobs = int($NumAlignJobs / 3);
		$Cpu_Align = int($Cpu_Node / $tmp_jobs);
		$AlignSem = int($Cpu_Node / $Cpu_Align);
	}
	else {
		# If using a manifest then we will only have 2 total jobs.
		# Therefore we take the $Cpu_Node / 2 to use for each job.
		$Cpu_Align = int($Cpu_Node / 2);
		$AlignSem = 2;
	}
#print "LINE 1338: AlignSem = \"$AlignSem\" Cpu_Align = \"$Cpu_Align\"\n";
}

my $semAlign = Thread::Semaphore->new($AlignSem);
my @AlignThreads;
open RPG, ">${BAM_PREFIX}_ReadsPerGene_input.txt"; # Contains all the info to run the &ReadsPerGene

#########
# Actually submit the jobs for alignment.
# If we're doing BWA we don't need to do anything special.

if ($UseStarManifest == 1 and $TI > 0) {
	push @FilesToCopy,"${LI}_${TI}_PE.ReadsPerGene.out.tab";  
	push @FilesToCopy,"${LI}_${TI}_SE.ReadsPerGene.out.tab";  
	print LOG "# FilesToCopy ${LI}_${TI}_PE.ReadsPerGene.out.tab\n";
	print LOG "# FilesToCopy ${LI}_${TI}_SE.ReadsPerGene.out.tab\n";
}

foreach (@FilesForAlign) {
	# Moved this here on 05/18/2017 because we need the $bwa_output variable to push these files into the @FilesToCopy
	if ($Aligner eq "STAR") {
		if ($UseStarManifest == 0) {
			($LI, $animal_id, $read_format, $base_file, $abbrev, $bwa_output, $for_file, $rev_file) = split(/\s/,$_);
			# for bwa the $bwa_output is HFD.89161.54348.R.AP.06.DUP.P.sam
			# for STAR we remove the 'sam' and use 'HFD.89161.54348.R.AP.06.DUP.P' as the --outFileNamePrefix
			$bwa_output =~ s/sam$//;
			# If we're doing a single tissue then we need the output from each file
			if ($TI > 0) { 															# Added logic 04/24/2021
				push @FilesToCopy,"${bwa_output}.ReadsPerGene.out.tab";  
				print LOG "# FilesToCopy ${bwa_output}.ReadsPerGene.out.tab\n";
			}
		}
=pod
		# If we're using a STAR manifest then there will always be ${LI}_${TI}_PE.ReadsPerGene.out.tab and ${LI}_${TI}_SE.ReadsPerGene.out.tab
		# So we'll just push those into @FilesToCopy before the @FilesForAlign loop
		else {
			if ($TI > 0) { 															# Added logic 04/24/2021
				push @FilesToCopy,"${LI}_${TI}.ReadsPerGene.out.tab";  
				print LOG "# FilesToCopy ${LI}_${TI}.ReadsPerGene.out.tab\n";



			}
		}
=cut
	}
	$semAlign->down;
	$t = threads->new(\&Alignment, $_);
	push (@AlignThreads,$t);
	sleep 1;
}
foreach (@AlignThreads) { my $num = $_->join; }

close RPG;

# NEW 04/24/2021
# New subroutine to process STAR output
# We only want to process the ReadsPerGene if we are doing a specific tissue.
# If $Analysis eq "rna" and there is no $TI specified then we are processing all $TI for genotyping

if ($Aligner eq "STAR" and $TI > 0) {
	print LOG "# FilesToCopy ${LI}.${TI}.ReadsPerGene.csv\n";
	print LOG "# FilesToCopy ${LI}.${TI}.${Date}_Upload_RNAcounts.sql\n";
	push @FilesToCopy,"${LI}.${TI}.ReadsPerGene.csv";
	push @FilesToCopy,"${LI}.${TI}.${Date}_Upload_RNAcounts.sql";
	&ReadsPerGene;
}

$TimeEnd = new Benchmark;
$TimeDiff = timediff($TimeEnd, $TimeStart);
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber ALIGN\tALL FILES\t", timestr($TimeDiff), "\n";
&DirectorySize;
system ("echo \"DONE ALIGN\" >DoneAlign");

sub Alignment {
=pod
Example below of a ${BAM_PREFIX}_BWA_input.txt file for a single lane of RNAseq.
There will always be multiple SE files in the ${BAM_PREFIX}_STAR_manifestSE.txt.
We only need to check how many lines are in the ${BAM_PREFIX}_STAR_manifestPE.txt
If there is a single entry then we can parse the @FilesForAlign2 array to match the PE file, which should only have one element.
The @FilesForAlign2 array has the same info as the @FilesForAlign array when $UseStarManifest == 0

cat 2922_4096_BWA_input.txt
2922 UMCUSAM000000002922 P AN.2922.4096.R.AP.01 aa AN.2922.4096.R.AP.01.P.sam AN.2922.4096.R.AP.01.1.P.fq AN.2922.4096.R.AP.01.2.P.fq
2922 UMCUSAM000000002922 P AN.2922.4096.R.AP.01 aa AN.2922.4096.R.AP.01.U1.sam AN.2922.4096.R.AP.01.1.U.fq
2922 UMCUSAM000000002922 P AN.2922.4096.R.AP.01 aa AN.2922.4096.R.AP.01.U2.sam AN.2922.4096.R.AP.01.2.U.fq
=cut
	my $line = $_;
	chomp $line;
	# If $UseStarManifest == 0 then $CurrentSTARmanifest will be meaningless.
	# If $UseStarManifest == 1 then $CurrentSTARmanifest will be the current manifest file name we are working with, either STARIPE or STARISE.
	my $CurrentSTARmanifest = $line; 
	# If $UseStarManifest == 1 and the $CurrentSTARmanifest only has 1 line then change this to 0 and treat the files as though no manifest.
	my $UseStarManifestTMP = 1;
	my $NumLinesInManifest = 0;
	my $ManifestRevFileName = ();
	if ($UseStarManifest == 1) {
		$NumLinesInManifest = `cat $CurrentSTARmanifest | wc -l`;
		chomp $NumLinesInManifest;
	}
#print "LINE 1431 NumLinesInManifest = \"$NumLinesInManifest\"\n";
	if ($NumLinesInManifest == 1) {
		$UseStarManifestTMP = 0;
		# Open the $CurrentSTARmanifest which has one line and looks like below.
		# AN.2922.4096.R.AP.01.1.P.fq     AN.2922.4096.R.AP.01.2.P.fq     ID:AN.2922.4096.R.AP.01 SM:UMCUSAM000000002922  LB:a    PL:ILLUMINA	
		# We need to grab the 2nd column for the reverse fastq file and use that to match the line in the @FilesForAlign2 array
		# To populate the variables to use instead of the manifest.
		$ManifestRevFileName = `awk '{print \$2}' $CurrentSTARmanifest`; #<<<<<<< PROBLEM HERE
		chomp $ManifestRevFileName;
#print "LINE 1439: ManifestRevFileName: \"$ManifestRevFileName\"\n";
		foreach (@FilesForAlign2) {
			my $line = $_;
			chomp $line;
#print "LINE 1446 line: \"$line\"\n";
			if ($line =~ m/$ManifestRevFileName/) {
				($LI, $animal_id, $read_format, $base_file, $abbrev, $bwa_output, $for_file, $rev_file) = split(/\s/,$line);
				# Only use the first character of $abbrev as the library identifier.
				# This properly identifies the library of origin so that files can be properly merged to run thru MarkDuplicates
				$lib = substr($abbrev,0,1);
			}
		}
		#print "\nLINE ~1453 \n";
		print "ManifestRevFileName = \"$ManifestRevFileName\"\n";
		print "bwa_output = \"$bwa_output\"\n";
		print "for_file = \"$for_file\"\n";
		print "rev_file = \"$rev_file\"\n";
		print "lib = \"$lib\"\n";
		print "\n";
	}

	#[0]$LI [1]$animal_id [2]$read_format [3]$abbrev [4]sam_out [5]for_file [6]rev_file
	if ($UseStarManifest == 0) {
		($LI, $animal_id, $read_format, $base_file, $abbrev, $bwa_output, $for_file, $rev_file) = split(/\s/,$line);
		# Only use the first character of $abbrev as the library identifier.
		# This properly identifies the library of origin so that files can be properly merged to run thru MarkDuplicates
		$lib = substr($abbrev,0,1);
	}

=pod
At the end of the above...
if $UseStarManifest == 0 then we proceed as normal
if $UseStarManifest == 1 AND we have a single line in the manifest then $UseStarManifestTMP = 0 and we proceed WITHOUT a manifest
if $UseStarManifest == 1 AND we have a multiple lines in the manifest then $UseStarManifestTMP = 1 and we proceed WITH a manifest
=cut

	#####
	# ACTUAL ALIGNMENT SECTIONS
	if ($Aligner eq 'BWA') {
		# Because BWA-MEM2 uses a different index we need to point to a different location if we're using V2
		# We leave open the possibility that a newer version will need a different location
		# Added 10/18/2020
		if ($BWA_version == 1) { $BWA_ref = "$RefGenome/${ref}"; }
		elsif ($BWA_version == 2) { $BWA_ref = "${RefGenome}/BWA2/${ref}.fa"; }
		else { $BWA_ref = "$RefGenome/${ref}"; }		# Change this if there is another version

		if ($read_format ne "S") {
			print "\nRunning: BWA $for_file $rev_file\n";
			if ($DoAlign == 1) {
				print LOG "$bwa mem -M -t $Cpu_Align -R '\@RG\\tID:${base_file}\\tSM:${animal_id}\\tLB:${lib}\\tPL:ILLUMINA' $BWA_ref $for_file $rev_file >$bwa_output\n";
				$Stage = "BWA $LI $TI $for_file";
				if ($DoneAlign == 0) {
					system ("$bwa mem -M -t $Cpu_Align -R '\@RG\\tID:${base_file}\\tSM:${animal_id}\\tLB:${lib}\\tPL:ILLUMINA' $BWA_ref $for_file $rev_file >$bwa_output");
					$CODE = __LINE__; &CheckExit;
				}
			}
			print SORTI "$LI $animal_id $read_format $abbrev $bwa_output\n";
			push @Files2DelAlign,"$bwa_output";
		}
		else {
			print "\nRunning: BWA $for_file\n";
			if ($DoAlign == 1) {
				print LOG "$bwa mem -M -t $Cpu_Align -R '\@RG\\tID:${base_file}\\tSM:${animal_id}\\tLB:${lib}\\tPL:ILLUMINA' $BWA_ref $for_file >$bwa_output\n";
				$Stage = "BWA $LI $TI $for_file";
				if ($DoneAlign == 0) {
					system ("$bwa mem -M -t $Cpu_Align -R '\@RG\\tID:${base_file}\\tSM:${animal_id}\\tLB:${lib}\\tPL:ILLUMINA' $BWA_ref $for_file >$bwa_output"); 	
					$CODE = __LINE__; &CheckExit;
				}
			}
			print SORTI "$LI $animal_id $read_format $abbrev $bwa_output\n";
			push @Files2DelAlign,"$bwa_output";
		}
	}	# END BWA

	if ($Aligner eq 'STAR') {
		if ($UseStarManifestTMP == 1) {
			print "\nRunning: STAR using manifest \"$CurrentSTARmanifest\"\n";

			# When using a manifest, we name the output file as ${BAM_PREFIX}_ and append SE or PE
			# NOTE: we add the '.' to the name here to keep it consisten with the way it works without a manifest.
			if ($UseStarManifest == 1) {
				if ($CurrentSTARmanifest eq "${BAM_PREFIX}_STAR_manifestSE.txt") { $STARoutFileNamePrefix = "${BAM_PREFIX}_SE."; }
				elsif ($CurrentSTARmanifest eq "${BAM_PREFIX}_STAR_manifestPE.txt") { $STARoutFileNamePrefix = "${BAM_PREFIX}_PE."; }
			}

			if ($DoAlign == 1) {
				if ($DoWasp == 1) {
					# ADD WASP TO THIS
					# EXITING because of FATAL INPUT ERROR: --waspOutputMode requires output to BAM file
					# SOLUTION: re-run STAR with --waspOutputMode ... and --outSAMtype BAM ...
					# EXITING because of fatal PARAMETER error: missing BAM option
					# SOLUTION: re-run STAR with one of the allowed values of --outSAMtype BAM Unsorted OR SortedByCoordinate OR both

					print LOG "$Star --runThreadN $Cpu_Align --genomeDir $RefGenome/STAR/$TaxonID/$InputRef --readFilesManifest $CurrentSTARmanifest --outFileNamePrefix ${STARoutFileNamePrefix} --waspOutputMode SAMtag --varVCFfile $WaspVCF --outSAMtype BAM Unsorted --outSAMattributes NH HI AS nM RG --outSAMmapqUnique 60 --outFilterType BySJout --outFilterMultimapNmax 20 --alignSJoverhangMin 8 --alignSJDBoverhangMin 1 --outFilterMismatchNmax 999 --alignIntronMin 20 --alignIntronMax 1000000 --alignMatesGapMax 1000000 --outMultimapperOrder Random --outSAMstrandField intronMotif --outSAMunmapped Within KeepPairs --quantMode GeneCounts --twopassMode Basic\n";
					$Stage = "STAR $LI $TI ${BAM_PREFIX}_STAR_manifest.txt";
					if ($DoneAlign == 0) {
						system ("$Star --runThreadN $Cpu_Align --genomeDir $RefGenome/STAR/$TaxonID/$InputRef --readFilesManifest $CurrentSTARmanifest --outFileNamePrefix ${STARoutFileNamePrefix} --waspOutputMode SAMtag --varVCFfile $WaspVCF --outSAMtype BAM Unsorted --outSAMattributes NH HI AS nM RG --outSAMmapqUnique 60 --outFilterType BySJout --outFilterMultimapNmax 20 --alignSJoverhangMin 8 --alignSJDBoverhangMin 1 --outFilterMismatchNmax 999 --alignIntronMin 20 --alignIntronMax 1000000 --alignMatesGapMax 1000000 --outMultimapperOrder Random --outSAMstrandField intronMotif --outSAMunmapped Within KeepPairs --quantMode GeneCounts --twopassMode Basic"); 
						$CODE = __LINE__; &CheckExit;
					}
				}	# WASP
				else {	# NoWasp
					print LOG "$Star --runThreadN $Cpu_Align --genomeDir $RefGenome/STAR/$TaxonID/$InputRef --readFilesManifest $CurrentSTARmanifest --outFileNamePrefix ${STARoutFileNamePrefix} --outSAMattributes NH HI AS nM RG --outSAMmapqUnique 60 --outFilterType BySJout --outFilterMultimapNmax 20 --alignSJoverhangMin 8 --alignSJDBoverhangMin 1 --outFilterMismatchNmax 999 --alignIntronMin 20 --alignIntronMax 1000000 --alignMatesGapMax 1000000 --outMultimapperOrder Random --outSAMstrandField intronMotif --outSAMunmapped Within KeepPairs --quantMode GeneCounts --twopassMode Basic\n";
					$Stage = "STAR $LI $TI ${BAM_PREFIX}_STAR_manifest.txt";
					if ($DoneAlign == 0) {
						system ("$Star --runThreadN $Cpu_Align --genomeDir $RefGenome/STAR/$TaxonID/$InputRef --readFilesManifest $CurrentSTARmanifest --outFileNamePrefix ${STARoutFileNamePrefix} --outSAMattributes NH HI AS nM RG --outSAMmapqUnique 60 --outFilterType BySJout --outFilterMultimapNmax 20 --alignSJoverhangMin 8 --alignSJDBoverhangMin 1 --outFilterMismatchNmax 999 --alignIntronMin 20 --alignIntronMax 1000000 --alignMatesGapMax 1000000 --outMultimapperOrder Random --outSAMstrandField intronMotif --outSAMunmapped Within KeepPairs --quantMode GeneCounts --twopassMode Basic"); 
						$CODE = __LINE__; &CheckExit;
					}
				}	#NoWAsp
			}	# DoAlign
			if ($DoWasp == 1) {
#				print SORTI "$LI $animal_id ALL ALL ${BAM_PREFIX}.Aligned.out.bam\n";
#				push @Files2DelAlign,"${BAM_PREFIX}.Aligned.out.bam";
				print SORTI "$LI $animal_id ALL ALL ${STARoutFileNamePrefix}Aligned.out.bam\n";
				push @Files2DelAlign,"${STARoutFileNamePrefix}Aligned.out.bam";
			}
			else {
#				print SORTI "$LI $animal_id ALL ALL ${BAM_PREFIX}.Aligned.out.sam\n";
#				push @Files2DelAlign,"${BAM_PREFIX}.Aligned.out.sam";
				print SORTI "$LI $animal_id ALL ALL ${STARoutFileNamePrefix}Aligned.out.sam\n";
				push @Files2DelAlign,"${STARoutFileNamePrefix}Aligned.out.sam";
			}
#			print RPG "${TaxonID},${InputRef},${Date},${LI},${TI},${animal_id},ALL,ALL,ALL,${BAM_PREFIX}.ReadsPerGene.out.tab\n";
			print RPG "${TaxonID},${InputRef},${Date},${LI},${TI},${animal_id},ALL,ALL,ALL,${STARoutFileNamePrefix}ReadsPerGene.out.tab\n";
		}	# END use manifest

		else {	# No manifest
#print "Currently running STAR No Manifest Line ~1611\n";
			if ($UseStarManifest == 1 and $UseStarManifestTMP == 0) {
				# When using a manifest and there is a single line in the manifest then we set $UseStarManifestTMP = 0
				# and we treat it as a "normal" run without a manifest. This means we will be relying on $bwa_output.
				# However, we need to name the output file as ${BAM_PREFIX}_ and append SE or PE to be consistent with using a manifest.
				if ($CurrentSTARmanifest eq "${BAM_PREFIX}_STAR_manifestSE.txt") { $STARoutFileNamePrefix = "${BAM_PREFIX}_SE."; }
				elsif ($CurrentSTARmanifest eq "${BAM_PREFIX}_STAR_manifestPE.txt") { $STARoutFileNamePrefix = "${BAM_PREFIX}_PE."; }
			}
			else {
				# If we are not using a manifest then we simply assign the $bwa_output value to $STARoutFileNamePrefix.
				# This way the --outFileNamePrefix uses $STARoutFileNamePrefix for both with and without manifest.
				$bwa_output =~ s/sam$//;	# for bwa the $bwa_output is HFD.89161.54348.R.AP.06.DUP.P.sam [note the dot '.' is left on the $bwa_output] 
				$STARoutFileNamePrefix = $bwa_output;
			}
			if ($read_format ne "S") {
				print "\nRunning: STAR $for_file $rev_file\n";
				if ($DoAlign == 1) {
					if ($DoWasp == 1) {
							print LOG "$Star --runThreadN $Cpu_Align --genomeDir $RefGenome/STAR/$TaxonID/$InputRef --readFilesIn $for_file $rev_file --outFileNamePrefix $STARoutFileNamePrefix --waspOutputMode SAMtag --varVCFfile $WaspVCF --outSAMtype BAM Unsorted --outSAMattrRGline ID:${base_file} SM:${animal_id} LB:${lib} PL:ILLUMINA --outSAMmapqUnique 60 --outFilterType BySJout --outFilterMultimapNmax 20 --alignSJoverhangMin 8 --alignSJDBoverhangMin 1 --outFilterMismatchNmax 999 --alignIntronMin 20 --alignIntronMax 1000000 --alignMatesGapMax 1000000 --outMultimapperOrder Random --outSAMstrandField intronMotif --outSAMunmapped Within KeepPairs --quantMode GeneCounts --twopassMode Basic\n";
							$Stage = "STAR $LI $TI $for_file";
							if ($DoneAlign == 0) {
								system ("$Star --runThreadN $Cpu_Align --genomeDir $RefGenome/STAR/$TaxonID/$InputRef --readFilesIn $for_file $rev_file --outFileNamePrefix $STARoutFileNamePrefix --waspOutputMode SAMtag --varVCFfile $WaspVCF --outSAMtype BAM Unsorted --outSAMattrRGline ID:${base_file} SM:${animal_id} LB:${lib} PL:ILLUMINA --outSAMmapqUnique 60 --outFilterType BySJout --outFilterMultimapNmax 20 --alignSJoverhangMin 8 --alignSJDBoverhangMin 1 --outFilterMismatchNmax 999 --alignIntronMin 20 --alignIntronMax 1000000 --alignMatesGapMax 1000000 --outMultimapperOrder Random --outSAMstrandField intronMotif --outSAMunmapped Within KeepPairs --quantMode GeneCounts --twopassMode Basic"); 
								$CODE = __LINE__; &CheckExit;
							}
					}	# WASP
					else {	# NO WASP
							print LOG "$Star --runThreadN $Cpu_Align --genomeDir $RefGenome/STAR/$TaxonID/$InputRef --readFilesIn $for_file $rev_file --outFileNamePrefix $STARoutFileNamePrefix --outSAMattrRGline ID:${base_file} SM:${animal_id} LB:${lib} PL:ILLUMINA --outSAMmapqUnique 60 --outFilterType BySJout --outFilterMultimapNmax 20 --alignSJoverhangMin 8 --alignSJDBoverhangMin 1 --outFilterMismatchNmax 999 --alignIntronMin 20 --alignIntronMax 1000000 --alignMatesGapMax 1000000 --outMultimapperOrder Random --outSAMstrandField intronMotif --outSAMunmapped Within KeepPairs --quantMode GeneCounts --twopassMode Basic\n";
							$Stage = "STAR $LI $TI $for_file";
							if ($DoneAlign == 0) {
								system ("$Star --runThreadN $Cpu_Align --genomeDir $RefGenome/STAR/$TaxonID/$InputRef --readFilesIn $for_file $rev_file --outFileNamePrefix $STARoutFileNamePrefix --outSAMattrRGline ID:${base_file} SM:${animal_id} LB:${lib} PL:ILLUMINA --outSAMmapqUnique 60 --outFilterType BySJout --outFilterMultimapNmax 20 --alignSJoverhangMin 8 --alignSJDBoverhangMin 1 --outFilterMismatchNmax 999 --alignIntronMin 20 --alignIntronMax 1000000 --alignMatesGapMax 1000000 --outMultimapperOrder Random --outSAMstrandField intronMotif --outSAMunmapped Within KeepPairs --quantMode GeneCounts --twopassMode Basic"); 
								$CODE = __LINE__; &CheckExit;
							}
					}
				}	# do align
				if ($DoWasp == 1) {
#					print SORTI "$LI $animal_id $read_format $abbrev ${bwa_output}Aligned.out.bam\n";
#					push @Files2DelAlign,"${bwa_output}Aligned.out.bam";
					print SORTI "$LI $animal_id $read_format $abbrev ${STARoutFileNamePrefix}Aligned.out.bam\n";
					push @Files2DelAlign,"${STARoutFileNamePrefix}Aligned.out.bam";
				}
				else {
#					print SORTI "$LI $animal_id $read_format $abbrev ${bwa_output}Aligned.out.sam\n";
#					push @Files2DelAlign,"${bwa_output}Aligned.out.sam";
					print SORTI "$LI $animal_id $read_format $abbrev ${STARoutFileNamePrefix}Aligned.out.sam\n";
					push @Files2DelAlign,"${STARoutFileNamePrefix}Aligned.out.sam";
				}
#				print RPG "${TaxonID},${InputRef},${Date},${LI},${TI},${animal_id},${base_file},${lib},${abbrev},${bwa_output}ReadsPerGene.out.tab\n";
				print RPG "${TaxonID},${InputRef},${Date},${LI},${TI},${animal_id},${base_file},${lib},${abbrev},${STARoutFileNamePrefix}ReadsPerGene.out.tab\n";
			}	# SE no manifest
			else {
				print "\nRunning: STAR $for_file\n";
				if ($DoAlign == 1) {
					if ($DoWasp == 1) {
						print LOG "$Star --runThreadN $Cpu_Align --genomeDir $RefGenome/STAR/$TaxonID/$InputRef --readFilesIn $for_file --outFileNamePrefix $STARoutFileNamePrefix --waspOutputMode SAMtag --varVCFfile $WaspVCF --outSAMtype BAM Unsorted --outSAMattrRGline ID:${base_file} SM:${animal_id} LB:${lib} PL:ILLUMINA --outSAMmapqUnique 60 --outFilterType BySJout --outFilterMultimapNmax 20 --alignSJoverhangMin 8 --alignSJDBoverhangMin 1 --outFilterMismatchNmax 999 --alignIntronMin 20 --alignIntronMax 1000000 --alignMatesGapMax 1000000 --outMultimapperOrder Random --outSAMstrandField intronMotif --outSAMunmapped Within KeepPairs --quantMode GeneCounts --twopassMode Basic\n";
						$Stage = "STAR $LI $TI $for_file";
						if ($DoneAlign == 0) {
							system ("$Star --runThreadN $Cpu_Align --genomeDir $RefGenome/STAR/$TaxonID/$InputRef --readFilesIn $for_file --outFileNamePrefix $STARoutFileNamePrefix --waspOutputMode SAMtag --varVCFfile $WaspVCF --outSAMtype BAM Unsorted --outSAMattrRGline ID:${base_file} SM:${animal_id} LB:${lib} PL:ILLUMINA --outSAMmapqUnique 60 --outFilterType BySJout --outFilterMultimapNmax 20 --alignSJoverhangMin 8 --alignSJDBoverhangMin 1 --outFilterMismatchNmax 999 --alignIntronMin 20 --alignIntronMax 1000000 --alignMatesGapMax 1000000 --outMultimapperOrder Random --outSAMstrandField intronMotif --outSAMunmapped Within KeepPairs --quantMode GeneCounts --twopassMode Basic");
							$CODE = __LINE__; &CheckExit;
						}
					}	# WASP
					else {	# NO WASP
						print LOG "$Star --runThreadN $Cpu_Align --genomeDir $RefGenome/STAR/$TaxonID/$InputRef --readFilesIn $for_file --outFileNamePrefix $STARoutFileNamePrefix --outSAMattrRGline ID:${base_file} SM:${animal_id} LB:${lib} PL:ILLUMINA --outSAMmapqUnique 60 --outFilterType BySJout --outFilterMultimapNmax 20 --alignSJoverhangMin 8 --alignSJDBoverhangMin 1 --outFilterMismatchNmax 999 --alignIntronMin 20 --alignIntronMax 1000000 --alignMatesGapMax 1000000 --outMultimapperOrder Random --outSAMstrandField intronMotif --outSAMunmapped Within KeepPairs --quantMode GeneCounts --twopassMode Basic\n";
						$Stage = "STAR $LI $TI $for_file";
						if ($DoneAlign == 0) {
							system ("$Star --runThreadN $Cpu_Align --genomeDir $RefGenome/STAR/$TaxonID/$InputRef --readFilesIn $for_file --outFileNamePrefix $STARoutFileNamePrefix --outSAMattrRGline ID:${base_file} SM:${animal_id} LB:${lib} PL:ILLUMINA --outSAMmapqUnique 60 --outFilterType BySJout --outFilterMultimapNmax 20 --alignSJoverhangMin 8 --alignSJDBoverhangMin 1 --outFilterMismatchNmax 999 --alignIntronMin 20 --alignIntronMax 1000000 --alignMatesGapMax 1000000 --outMultimapperOrder Random --outSAMstrandField intronMotif --outSAMunmapped Within KeepPairs --quantMode GeneCounts --twopassMode Basic");
							$CODE = __LINE__; &CheckExit;
						}
					}	# NO WASP
				}	# do align
				if ($DoWasp == 1) {
#					print SORTI "$LI $animal_id $read_format $abbrev ${bwa_output}Aligned.out.bam\n";
#					push @Files2DelAlign,"${bwa_output}.Aligned.out.bam";
					print SORTI "$LI $animal_id $read_format $abbrev ${STARoutFileNamePrefix}Aligned.out.bam\n";
					push @Files2DelAlign,"${STARoutFileNamePrefix}.Aligned.out.bam";
				}
				else {
#					print SORTI "$LI $animal_id $read_format $abbrev ${bwa_output}Aligned.out.sam\n";
#					push @Files2DelAlign,"${bwa_output}.Aligned.out.sam";
					print SORTI "$LI $animal_id $read_format $abbrev ${STARoutFileNamePrefix}Aligned.out.sam\n";
					push @Files2DelAlign,"${STARoutFileNamePrefix}Aligned.out.sam";
				}
#				print RPG "${TaxonID},${InputRef},${Date},${LI},${TI},${animal_id},${base_file},${lib},${abbrev},${bwa_output}ReadsPerGene.out.tab\n";
				print RPG "${TaxonID},${InputRef},${Date},${LI},${TI},${animal_id},${base_file},${lib},${abbrev},${STARoutFileNamePrefix}ReadsPerGene.out.tab\n";
			}	# PE no manifest
		}	# No manifest
	}	# Star alignment
#
	$semAlign->up;
}

close SORTI;


###############################################################################
# Now that alignment is done it's safe to delete the output files from trimming
print LOG "# DELETING FASTQ FILES\n";
print LOG "rm -f *.fq\n";
system ("rm -f *.fq");

###############################################################################
# SAMTOOLS SORT
# ${BAM_PREFIX}_SORT_input.txt contains the information necessary to run samtools sort
# Count the number of files that need to be sorted to determine RAM per samtools thread and semaphore
# The way we refactored using a STAR manifest, there should always be at least two files in ${BAM_PREFIX}_SORT_input.txt

if ($DoneSort1 == 1) { print LOG "# SortFiles ALREADY DONE\n"; }
open SORTI, "<${BAM_PREFIX}_SORT_input.txt";
open MERGEI, ">${BAM_PREFIX}_MERGE_input.txt";
$SortFiles = `cat ${BAM_PREFIX}_SORT_input.txt | wc -l`;
chomp $SortFiles;
print "SortFiles:\t$SortFiles\n";
print LOG "# SortFiles:\t$SortFiles\n";

&Memory;	# Grab the total amount of memory on the node

my $SortSem = 1;
if (int($Cpu_Node / 4) > 1 ) {
	$Cpu_Samtools = 4;
	if ($SortFiles < 4) { $SortSem = $SortFiles; }
	else { $SortSem = 4; }
	
	# Running out of memory if there was a single sam file so we reduce the MemTotal by 10G 
	# (changed from 5 to 10 07/13/2019) Changed from 10 to 20G 11/04/2019
	# so when samtools spawns 4 threads there is some overhead for the OS. 07/04/2019
	# 04/19/2021
	# samtools actually uses ~12% more memory than specified. For example, with 30G/thread and 4 threads
	# it was using up to 132G based on top for a large file. 
	# Therefore, we subtract this 12% factor from the numberator $MemTotal.
	$MemTotal = $MemTotal - 20;
	print "MemTotal\t$MemTotal\n";
	$SortMemPerSem = floor(($MemTotal * 0.88) / ($Cpu_Samtools * $SortSem)); # Changed 04/19/2021
	print "SortSem\t$SortSem\n";
	print "SortMemPerSem:\t$SortMemPerSem\n";
	print LOG "# MemTotal\t$MemTotal\n";
	print LOG "# Cpu_Samtools\t$Cpu_Samtools\n";
	print LOG "# SortSem\t$SortSem\n";
	print LOG "# SortMemPerSem:\t$SortMemPerSem\n";
	# need to consider how much total mem is allocated based on threads and semaphores 
	# Changed from 4 to 8 to try to use more CPU 07/13/2018
	# samtools sort was taking much too long so changed this back to 4 which allows more mem/thread 08/27/18
}

while (<SORTI>) {
	my $line = $_;
	chomp $line;
	#[0]$LI [1]$animal_id [2]$read_format [3]$abbrev [4]sam_input
	my ($LI, $animal_id, $read_format, $abbrev, $sam_input) = split(/\s/,$line);
	my $lib = substr($abbrev,0,1);

	# For STAR with manifest and WASP the output file is *.Aligned.out.bam, which populates $sam_input
	# So we need to add another substitution here |.Aligned.out.bam, otherwise the input and output are the same and overwrite each other.
	my $sort_output = $sam_input;
	$sort_output =~ s/.sam|.Aligned.out.sam|.Aligned.out.bam/.sorted.bam/;

	# Files larger than -m xG will spill to disk during sort.
	# 02/28/2018 changed -l from 0 to 2 to do minimal compression. This was going slow and having too high %wa and not using available cores
	# 06/10/2018 removed -l to produce compressed files
	# -m is per thread so need to multiple by the number of threads and number of semaphores
	# with -m 10G and 8 threads that's 80G per semaphore so we can only do 6 semaphores
	# 08/27/2018 changed back to 4 threads to allow more mem.
	# With 500G ram / 4 threads = 125G / file. So with 2 semaphores we need to use $SortMem=62G. 
	# $SortMemPerSem added 06/04/2019 to handle allocating ram/thread 

	# 04/13/2021
	# If a previous run failed and there were leftover ${sam_input}.TMP files present then samtools will fail with error:
	# "samtools sort: failed to create temporary file "UNK.341077.AP.01.P.sam.TMP.0000.bam": File exists"
	# This is a known issue https://github.com/samtools/samtools/issues/1035
	# Until this gets resolved we'll just automatically delete all ${sam_input}.TMP.*.bam files.
	# We don't check the exit code here because we expect this to fail if there were no tmp files.
	# This ^^ was fixed Oct6 2021 https://github.com/samtools/samtools/pull/1510
	# system ("rm ${sam_input}.TMP.*.bam");
	
	push (@SortString, "$Samtools sort -m ${SortMemPerSem}G -\@ $Cpu_Samtools -o $sort_output -T ${sam_input}.TMP $sam_input");

	# When using a STAR manifest we will always have two bam files to sort *SE.Aligned.out.bam and *PE.Aligned.out.bam
	# However, there is no library specific files since these were accounted for with the @RG tags in the manifest.
	# Therefore, we just need to write each file to the MERGEI file so we can merge the two later,
	# And we assign a dummy library 'A' to the last field of MERGEI
	if ($UseStarManifest == 1) {
		print MERGEI "$LI $animal_id $sort_output A\n";
	}
	else {
		print MERGEI "$LI $animal_id $sort_output $lib\n";
	}
	push @Files2DelSort,"$sort_output";
}
close SORTI;
close MERGEI;

$StageNumber++;
$TimeStart = new Benchmark;
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber SAMTOOLS SORT\tALL FILES\t\t\n";
print LOG "# SAMTOOLS SORT\n";

my $semSamtools = Thread::Semaphore->new($SortSem);
my @SortThreads;

foreach (@SortString) {
	$semSamtools->down;
	$t = threads->new(\&Sort, $_);
	push(@SortThreads,$t);
	sleep 1;
}
foreach (@SortThreads) { my $num = $_->join; }

$TimeEnd = new Benchmark;
$TimeDiff = timediff($TimeEnd, $TimeStart);
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber SAMTOOLS SORT\tALL FILES\t", timestr($TimeDiff), "\n";
&DirectorySize;
system ("echo \"DONE SAMTOOLS SORT1\" >DoneSort1");

sub Sort {
	print "SAMTOOLS SORT \n";
	print LOG "$_\n";
	$Stage = "$LI $TI SAMTOOLS SORT1 ";
	if ($DoneSort1 == 0) {
		print "$_\n";
		system ("$_");
		$CODE = __LINE__; &CheckExit;
	}
	$semSamtools->up;
}

###############################################################################
# Now that Sorting is done it's safe to delete the output files from alignment
# If restarting and the previous sort stage was completed ($DoneSort1 = 1)
# then we don't want to do this because later on the $BAM_PREFIX.links.sam will get deleted
# We only want to delete these if we did the previous step in this run ($DoneSort1 == 0)
print LOG "# DELETING SAM FILES\n";
print LOG "rm *.sam\n";
if ($DoneSort1 == 0) { system ("rm *.sam"); }

###############################################################################
# PICARD MERGE
# !!!!!!!!!!!!!!!!!!!!!!!!
# DON'T USE samtools merge because it does not handle the read groups correctly with our data
# !!!!!!!!!!!!!!!!!!!!!!!!
# samtools merge was artificially adding read groups to prevent collisions when merging files from the same library.
# The -c option of samtools merge only uses the @RG from the first file in the file list which removed any SM tags present.
# picard MergeSamFiles will maintain the proper @RG

# MERGE_input.txt contains the information necessary to run picard merge
# When using STAR manifest, there are exactly two sorted bam files produced for PE & SE and we assigned both to library 'A',
#  even if there are multiple libraries represented. Therefore, since there will not be multiple library specific bams,
#  we cannot use the normal code to loop through @Unique_Libraries since this will still contain all the unique libraries. 
#  So we have a separate block to just merge the two STAR manifest bam files.
# open output filehandle for each unique library
if ($UseStarManifest == 0) {
	foreach (@Unique_Libraries) { open "MERGE${_}", ">${BAM_PREFIX}_${_}_MERGE_files.txt"; }

	open MERGEI, "<${BAM_PREFIX}_MERGE_input.txt";
	while (<MERGEI>) {
		my $line = $_;
		chomp $line;
		#[0]$LI [1]$animal_id [2]$sort_output [3]$lib
		my ($LI, $animal_id, $sort_output, $lib) = split(/\s/,$line);
		push (@{"sorted_bam_picard_$lib"}, "I=${sort_output}");	#input file array for picard merge
		print {"MERGE${lib}"} "INPUT=${sort_output} \n";		# write the INPUT:file_name so that it can be read
	}
	close MERGEI;
	# close output filehandle for each unique library
	foreach (@Unique_Libraries) { close "MERGE${_}"; }

	$StageNumber++;
	$TimeStart = new Benchmark;
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber PICARD MERGE\tLIBRARY FILES\t\t\n";
	print LOG "# PICARD MERGE\n";
	if ($DonePicardMerge == 1) { print LOG "# PICARD MERGE ALREADY DONE\n"; }

	# $PicardMergeSem needs to be at least the number of libraries
	my $PicardMergeSem = 1;
	if (int($Cpu_Node / $NumLibraries) > 1 ) { $PicardMergeSem = int($Cpu_Node / $NumLibraries); }

	my @MergeThreads;
	$semPicardMerge = Thread::Semaphore->new($PicardMergeSem);	
	foreach (@Unique_Libraries) {
		$semPicardMerge->down;
		$t = threads->new(\&Merge, $_);
		push(@MergeThreads,$t);
		push @Files2DelMerge,"${BAM_PREFIX}.${_}.merged.bam";
		sleep 1;
	}
	foreach (@MergeThreads) { my $num = $_->join; }

	$TimeEnd = new Benchmark;
	$TimeDiff = timediff($TimeEnd, $TimeStart);
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber PICARD MERGE\tLIBRARY FILES\t", timestr($TimeDiff), "\n";
	&DirectorySize;
	system ("echo \"DONE Picard Merge\" >DonePicardMerge");
}
elsif ($UseStarManifest == 1) {
	open MERGEI, "<${BAM_PREFIX}_MERGE_input.txt";
	while (<MERGEI>) {
		my $line = $_;
		chomp $line;
		#[0]$LI [1]$animal_id [2]$sort_output [3]$lib <<-- $lib will be 'A' for both but doesn't represent the actual library
		my ($LI, $animal_id, $sort_output, $lib) = split(/\s/,$line);
		push (@StarManifestMergeBams, "I=${sort_output}");	#input file array for picard merge
	}
	close MERGEI;

	print LOG "# STAR manifest merging \n";
	print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx20g -jar $Picard MergeSamFiles @StarManifestMergeBams OUTPUT=${BAM_PREFIX}.merged.bam USE_THREADING=TRUE MERGE_SEQUENCE_DICTIONARIES=TRUE ASSUME_SORTED=TRUE VALIDATION_STRINGENCY=LENIENT TMP_DIR=${cwd}/tmp \n";
	if ($DonePicardMerge == 0) {
		system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx20g -jar $Picard MergeSamFiles @StarManifestMergeBams OUTPUT=${BAM_PREFIX}.merged.bam USE_THREADING=TRUE MERGE_SEQUENCE_DICTIONARIES=TRUE ASSUME_SORTED=TRUE VALIDATION_STRINGENCY=LENIENT TMP_DIR=${cwd}/tmp "); 
		$CODE = __LINE__; &CheckExit;
	}
	push @Files2DelMerge,"${BAM_PREFIX}.merged.bam";
	system ("echo \"DONE Picard Merge\" >DonePicardMerge");
}

sub Merge {
	print "PICARD MERGE ${BAM_PREFIX}_${_}_MERGE_files.txt\n";
	# @in contains the input files for each library
	my @in = @{"sorted_bam_picard_$_"};

	# Uncompressed output
	# Added ASSUME_SORTED=TRUE 04/20/2016
	# Added VALIDATION_STRINGENCY=LENIENT 06/24/2016 because some RNAseq data was throwing errors "Not primary alignment flag should not be set for unmapped read"
	# https://sourceforge.net/p/picard/wiki/Main_Page/#q-why-am-i-getting-errors-from-picard-like-mapq-should-be-0-for-unmapped-read-or-cigar-should-have-zero-elements-for-unmapped-read
	# 06/10/2018 Removed COMPRESSION_LEVEL=0

	# Changed GC threads from 2 to 6 07/13/2018
	print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx20g -jar $Picard MergeSamFiles @in OUTPUT=${BAM_PREFIX}.${_}.merged.bam USE_THREADING=TRUE MERGE_SEQUENCE_DICTIONARIES=TRUE ASSUME_SORTED=TRUE VALIDATION_STRINGENCY=LENIENT TMP_DIR=${cwd}/tmp \n";
	if ($DonePicardMerge == 0) {
		system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx20g -jar $Picard MergeSamFiles @in OUTPUT=${BAM_PREFIX}.${_}.merged.bam USE_THREADING=TRUE MERGE_SEQUENCE_DICTIONARIES=TRUE ASSUME_SORTED=TRUE VALIDATION_STRINGENCY=LENIENT TMP_DIR=${cwd}/tmp "); 
		$CODE = __LINE__; &CheckExit;
	}
	$semPicardMerge->up;
}

###############################################################################
# Now that Merging is done it's safe to delete the output files from Sorting
print LOG "# DELETING SORTED BAM FILES\n";
foreach (@Files2DelSort) {
	print LOG "rm $_\n";
	system ("rm $_");
}

if ($Analysis eq 'rna') {
	print LOG "rm -rf *STARpass1\n";
	print LOG "rm -rf *STARgenome\n";
	system ("rm -rf *STARpass1");
	system ("rm -rf *STARgenome");
}

###############################################################################
# MARK DUPS
# specifying more mem -Xmx50g and setting SORTING_COLLECTION_SIZE_RATIO=0.50 MAX_RECORDS_IN_RAM=1000000 *doubled* the run time
# https://sourceforge.net/p/picard/wiki/Main_Page/
# A rule of thumb for reads of ~100bp is to set MAX_RECORDS_IN_RAM to be 250,000 reads per each GB given to the -Xmx parameter for SortSam.

$StageNumber++;
$TimeStart = new Benchmark;
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber PICARD MARK DUPS\tALL FILES\t\t\n";
print "PICARD MARK DUPS ${BAM_PREFIX}.merged.bam\n";
print LOG "# PICARD MARK DUPS\n";
if ($DoneMarkDups == 1) { print LOG "# PICARD MARK DUPS ALREADY DONE\n"; }

if ($UseStarManifest == 0) {
	# We need at least as many semaphores as libraries
	my $PicardDupsSem = 1;
	if (int($Cpu_Node / $NumLibraries) > 1 ) { $PicardDupsSem = int($Cpu_Node / $NumLibraries); }

	$semMarkDups = Thread::Semaphore->new($PicardDupsSem);
	my @MarkDupsThreads;

	foreach (@Unique_Libraries) {
		$semMarkDups->down;
		$t = threads->new(\&MarkDups, $_);
		push(@MarkDupsThreads,$t);
		push @Files2DelMarkDups,"${BAM_PREFIX}.${_}.bam";
		# 08/14/2017 Moved to here because it wasn't getting added to @FilesToCopy array when in subroutine
		push (@FilesToCopy, "${BAM_PREFIX}.${_}.DUP.METRICS");	
		sleep 1;
	}
	foreach (@MarkDupsThreads) { my $num = $_->join; }

	$TimeEnd = new Benchmark;
	$TimeDiff = timediff($TimeEnd, $TimeStart);
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber PICARD MARK DUPS\t${BAM_PREFIX}.library.merged.bam\t", timestr($TimeDiff), "\n";
	&DirectorySize;
	system ("echo \"DONE MarkDups\" >DoneMarkDups");
}

sub MarkDups {
	print "PICARD MARK DUPS\t${BAM_PREFIX}_${_}_MERGE_files.txt ${BAM_PREFIX}.${_}.merged.bam\n";
	# Had to add MAX_FILE_HANDLES_FOR_READ_ENDS_MAP=1000 because some files (particularly short reads) were opening too many tmp files and dying
	# Changed MAX_RECORDS_IN_RAM from 1M to 5M and added ASSUME_SORTED=true 04/20/2016
	# removed COMPRESSION_LEVEL=0 06/17/2018
	# Added back COMPRESSION_LEVEL=0 07/13/2018 this significantly sped up MarkDuplicates because it doesn't have to compress the output
	# Changed GC threads from 2 to 6 and mem from 20g to 50g 07/13/2018 
	$Pixels = $LibPixels{$_};
	print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=6 -Xmx50g -jar $Picard MarkDuplicates -INPUT ${BAM_PREFIX}.${_}.merged.bam -OUTPUT ${BAM_PREFIX}.${_}.bam -METRICS_FILE ${BAM_PREFIX}.${_}.DUP.METRICS -MAX_RECORDS_IN_RAM 5000000 -MAX_FILE_HANDLES_FOR_READ_ENDS_MAP 1000 -ASSUME_SORTED TRUE -VALIDATION_STRINGENCY LENIENT -TMP_DIR ${cwd}/tmp -OPTICAL_DUPLICATE_PIXEL_DISTANCE ${Pixels} -COMPRESSION_LEVEL 0\n"; 
	$Stage = "$LI $TI PICARD MARK DUPS $_";
	if ($DoneMarkDups == 0) {
		system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=6 -Xmx50g -jar $Picard MarkDuplicates -INPUT ${BAM_PREFIX}.${_}.merged.bam -OUTPUT ${BAM_PREFIX}.${_}.bam -METRICS_FILE ${BAM_PREFIX}.${_}.DUP.METRICS -MAX_RECORDS_IN_RAM 5000000 -MAX_FILE_HANDLES_FOR_READ_ENDS_MAP 1000 -ASSUME_SORTED TRUE -VALIDATION_STRINGENCY LENIENT -TMP_DIR ${cwd}/tmp -OPTICAL_DUPLICATE_PIXEL_DISTANCE ${Pixels} -COMPRESSION_LEVEL 0"); 
		$CODE = __LINE__; &CheckExit;
	}
	$semMarkDups->up;
}

# This added 11/04/2022 
if ($UseStarManifest == 1) {
	# Since using STAR manifest only produces one BAM file we don't need to do anything with semaphores.
	# We just need to run one MarkDups.
	# The output from a normal MarkDups run is ${BAM_PREFIX}.${_}.bam for each library,
	# which then gets merged to produce a final bam as ${BAM_PREFIX}.bam.
	# Since we're not doing library specific nor merging, we'll just output the ${BAM_PREFIX}.bam here for MarkDups.

	print "PICARD MARK DUPS ${BAM_PREFIX}.merged.bam\n";
	$Pixels = $MaxPixelDistance;
	print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=6 -Xmx50g -jar $Picard MarkDuplicates -INPUT ${BAM_PREFIX}.merged.bam -OUTPUT ${BAM_PREFIX}.bam -METRICS_FILE ${BAM_PREFIX}.DUP.METRICS -MAX_RECORDS_IN_RAM 5000000 -MAX_FILE_HANDLES_FOR_READ_ENDS_MAP 1000 -ASSUME_SORTED TRUE -VALIDATION_STRINGENCY LENIENT -TMP_DIR ${cwd}/tmp -OPTICAL_DUPLICATE_PIXEL_DISTANCE ${Pixels} -COMPRESSION_LEVEL 0\n"; 
	$Stage = "$LI $TI PICARD MARK DUPS merged";
	if ($DoneMarkDups == 0) {
		system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=6 -Xmx50g -jar $Picard MarkDuplicates -INPUT ${BAM_PREFIX}.merged.bam -OUTPUT ${BAM_PREFIX}.bam -METRICS_FILE ${BAM_PREFIX}.DUP.METRICS -MAX_RECORDS_IN_RAM 5000000 -MAX_FILE_HANDLES_FOR_READ_ENDS_MAP 1000 -ASSUME_SORTED TRUE -VALIDATION_STRINGENCY LENIENT -TMP_DIR ${cwd}/tmp -OPTICAL_DUPLICATE_PIXEL_DISTANCE ${Pixels} -COMPRESSION_LEVEL 0"); 
		$CODE = __LINE__; &CheckExit;
	}
	push (@FilesToCopy, "${BAM_PREFIX}.DUP.METRICS");
	$TimeEnd = new Benchmark;
	$TimeDiff = timediff($TimeEnd, $TimeStart);
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber PICARD MARK DUPS\t${BAM_PREFIX}.library.merged.bam\t", timestr($TimeDiff), "\n";
	&DirectorySize;
	system ("echo \"DONE MarkDups\" >DoneMarkDups");
}

###############################################################################
# Now that MarkDuplicates is done it's safe to delete the output files from Sorting
print LOG "# DELETING MERGED BAM FILES\n";
foreach (@Files2DelMerge) {
	print LOG "rm $_\n";
	system ("rm $_");
}
@Files2DelMerge = ();

###############################################################################
###############################################################################
# SAMTOOLS MERGE
# MERGE_input.txt contains the information necessary to run samtools merge
# write list of files to merge

# 07/13/18 with the MarkDups bam file being uncompressed the sort can use more threads. This was using all 10 so increase
# 01/04/19 samtools merge was taking way too long on Lewis and was never using 20 threads.
# Tested this on MUG07 and it appears that it only uses about 10 cores even if given 20 so change this to 10.
if (int($Cpu_Node / 10) > 1 ) { $Cpu_Samtools = 10; }

$StageNumber++;
$TimeStart = new Benchmark;
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber SAMTOOLS MERGE\tALL FILES\t\t\n";
print LOG "# SAMTOOLS MERGE\n";
if ($DoneMergeDups == 1) { print LOG "# SAMTOOLS MERGE ALREADY DONE\n"; }

# We need to check if there is more than one library because with a single library there is nothing to merge,
# and if we're using STAR manifest then there is nothing to merge but the $NumLibraries might be >1,
# so we add the additional condition that $UseStarManifest == 0.
if ($NumLibraries > 1 and $UseStarManifest == 0) {
	open MERGE, ">${BAM_PREFIX}_MERGE_files.txt";
	foreach (@Unique_Libraries) { print MERGE "${BAM_PREFIX}.${_}.bam\n"; }
	close MERGE;
	print "SAMTOOLS MERGE BAM\n";
	# -u Uncompressed output, probably don't need @ 10 because it looks like this is single threaded when writing uncompressed output
	# 05/23/2018 Added -p option to Combine PG tags with colliding IDs rather than adding a suffix to differentiate them
	# 06/10/2018 Removed -u uncompressed flag
	print LOG "$Samtools merge -\@ $Cpu_Samtools -p -f -b ${BAM_PREFIX}_MERGE_files.txt ${BAM_PREFIX}.bam\n";
	$Stage = "$StageNumber $LI $TI SAMTOOLS MERGE";
	if ($DoneMergeDups == 0) {
		system ("$Samtools merge -\@ $Cpu_Samtools -p -f -b ${BAM_PREFIX}_MERGE_files.txt ${BAM_PREFIX}.bam");
		$CODE = __LINE__; &CheckExit;
	}
	push @Files2DelMarkDups,"${BAM_PREFIX}.bam";
}
# If there is only a single library we need to rename the ${BAM_PREFIX}.[unique_library].bam to what the merge file would be ${BAM_PREFIX}.bam
# Since there is only one library it will be the 0 element in @Unique_Libraries,
# however, if $UseStarManifest == 1 then we still have a single file but the name is different.
else {
	$Stage = "$StageNumber $LI $TI SAMTOOLS MERGE";
	if ($UseStarManifest == 0) {
		print LOG "system (mv ${BAM_PREFIX}.$Unique_Libraries[0].bam ${BAM_PREFIX}.bam)\n";
		if ($DoneMergeDups == 0) {
			system ("mv ${BAM_PREFIX}.$Unique_Libraries[0].bam ${BAM_PREFIX}.bam");
			$CODE = __LINE__; &CheckExit;
		}
	}
	######
	# if $UseStarManifest == 1 
	# then we already specified the output of MarkDups to be ${BAM_PREFIX}.bam around line 1757
	# so there's nothing to do here
	######
	push @Files2DelMarkDups,"${BAM_PREFIX}.bam";
}

$TimeEnd = new Benchmark;
$TimeDiff = timediff($TimeEnd, $TimeStart);
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber SAMTOOLS MERGE\t${BAM_PREFIX}.bam\t", timestr($TimeDiff), "\n";
&DirectorySize;
system ("echo \"DONE MergeDups\" >DoneMergeDups");

###############################################################################
# INDEX BAM
$StageNumber++;
$TimeStart = new Benchmark;
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber SAMTOOLS INDEX\tALL FILES\t\t\n";

print "SAMTOOLS INDEX BAM ${BAM_PREFIX}.bam\n";
print LOG "# SAMTOOLS INDEX\n";
if ($DoneIndexDups == 1) { print LOG "# SAMTOOLS INDEX ALREADY DONE\n"; }
print LOG "$Samtools index -\@ 8 ${BAM_PREFIX}.bam\n";
$Stage = "$StageNumber $LI $TI SAMTOOLS INDEX";
if ($DoneIndexDups == 0) {
	system ("$Samtools index -\@ 8 ${BAM_PREFIX}.bam");
	$CODE = __LINE__; &CheckExit;
}
$TimeEnd = new Benchmark;
$TimeDiff = timediff($TimeEnd, $TimeStart);
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber SAMTOOLS INDEX\t${BAM_PREFIX}.bam\t", timestr($TimeDiff), "\n";
&DirectorySize;
system ("echo \"DONE IndexDups\" >DoneIndexDups");

###############################################################################
# Adding "unmapped" lower case to @SeqForIndelTargetX causes issues for GATK walkers that need mapped reads using -L operations
# https://software.broadinstitute.org/gatk/documentation/tooldocs/3.8-0/org_broadinstitute_gatk_engine_CommandLineGATK.php#--intervals
# The unmapped paired reads were getting lost from the bam file so we extract them here to their own file.
# Extract unmapped reads for future use
# https://broadinstitute.github.io/picard/explain-flags.html
#

$StageNumber++;
$TimeStart = new Benchmark;
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber EXTRACT UNPAIRED1\tALL FILES\t\t\n";
print LOG "# EXTRACT UNPAIRED1\n";
if ($DoneUnmapped == 1) { print LOG "# EXTRACT UNPAIRED1 ALREADY DONE\n"; }

# At this stage all reads have been aligned and went thru MarkDups
# Extract reads where both reads are present and unmapped
# The ${BAM_PREFIX}.Unmapped.bam output file from this is needed for subsequent commands so we run this first outside the semaphores
# -f 12 read unmapped (0x4), mate unmapped (0x8)
print LOG "$Samtools view -h -f 12 -F 0x900 -\@ $Cpu_Unpaired ${BAM_PREFIX}.bam -b -o ${BAM_PREFIX}.Unmapped.bam\n";
$Stage = "$StageNumber $LI $TI EXTRACT UNMAPPED PAIRS";
if ($DoneUnmapped == 0) {
	system ("$Samtools view -h -f 12 -F 0x900 -\@ $Cpu_Unpaired ${BAM_PREFIX}.bam -b -o ${BAM_PREFIX}.Unmapped.bam");
	$CODE = __LINE__; &CheckExit;
}
print LOG "md5sum ${BAM_PREFIX}.Unmapped.bam >${BAM_PREFIX}.Unmapped.bam.md5\n";
if ($DoneUnmapped == 0) {
	system ("md5sum ${BAM_PREFIX}.Unmapped.bam >${BAM_PREFIX}.Unmapped.bam.md5");
	$CODE = __LINE__; &CheckExit;
}
push (@FilesToCopy, "${BAM_PREFIX}.Unmapped.bam");
push (@FilesToCopy, "${BAM_PREFIX}.Unmapped.bam.md5");

my $UnpairedSem = 1;
if (int($Cpu_Node / 4) > 1 ) {
	$Cpu_Unpaired = 4;
	$UnpairedSem = 4;
}

# -f 12 read unmapped, mate unmapped
# -f 68 INCLUDE read unmapped, first in pair
# -F 8 EXCLUDE mate unmapped
# -f 132 INCLUDE read unmapped, second in pair
# -f 8 INCLUDE mate unmapped
# -F 4 EXCLUDE read unmapped
# -F 0x900 EXCLUDE not primary alignment (0x100) and supplementary alignment (0x800)
# From samtools manual: 
# The default value for the -F option should really be 0x900 so that secondary and supplementary reads are automatically excluded.
# The existing default of 0 is retained for reasons of compatibility

# ${BAM_PREFIX}.MateUnmapped.1.fastq.gz and reverse contain paired reads where neither map to reference
# ${BAM_PREFIX}.MateMapped.1.fastq.gz Forward read unmapped but Reverse IS mapped
# ${BAM_PREFIX}.MateMapped.2.fastq.gz Reverse read unmapped but Forward IS mapped
# ${BAM_PREFIX}.links.sam
@UnpairedString = ();
push (@UnpairedString,"$Samtools fastq -f 12 -F 0x900 -c 9 -\@ $Cpu_Unpaired -1 ${BAM_PREFIX}.MateUnmapped.1.fastq.gz -2 ${BAM_PREFIX}.MateUnmapped.2.fastq.gz -0 /dev/null -s /dev/null ${BAM_PREFIX}.Unmapped.bam ");
push (@UnpairedString,"$Samtools fastq -f 68 -F 8 -F 0x900 -c 9 -\@ $Cpu_Unpaired ${BAM_PREFIX}.bam -1 ${BAM_PREFIX}.MateMapped.1.fastq.gz ");
push (@UnpairedString,"$Samtools fastq -f 132 -F 8 -F 0x900 -c 9 -\@ $Cpu_Unpaired ${BAM_PREFIX}.bam -2 ${BAM_PREFIX}.MateMapped.2.fastq.gz ");
push (@UnpairedString,"$Samtools view -f 8 -F 4 -F 0x900 -\@ $Cpu_Unpaired ${BAM_PREFIX}.bam > ${BAM_PREFIX}.links.sam ");

my $semUnpaired = Thread::Semaphore->new($UnpairedSem);
my @UnpairedThreads;

foreach (@UnpairedString) {
	$semUnpaired->down;
	$t = threads->new(\&Unpaired, $_);
	push(@UnpairedThreads,$t);
	sleep 0.5;
}
foreach (@UnpairedThreads) { my $num = $_->join; }

sub Unpaired {
	print "EXTRACT UNPAIRED \n";
	print LOG "$_\n";
	$Stage = "$StageNumber $LI $TI EXTRACT UNPAIRED READS";
	if ($DoneUnmapped == 0) {
		system ("$_");
		$CODE = __LINE__; &CheckExit;
	}
	$semUnpaired->up;
}

print LOG "md5sum ${BAM_PREFIX}.MateUnmapped.1.fastq.gz >${BAM_PREFIX}.MateUnmapped.1.fastq.gz.md5 \n";
if ($DoneUnmapped == 0) {
	system ("md5sum ${BAM_PREFIX}.MateUnmapped.1.fastq.gz >${BAM_PREFIX}.MateUnmapped.1.fastq.gz.md5");
	$CODE = __LINE__; &CheckExit;
}
print LOG "md5sum ${BAM_PREFIX}.MateUnmapped.2.fastq.gz >${BAM_PREFIX}.MateUnmapped.2.fastq.gz.md5 \n";
if ($DoneUnmapped == 0) {
	system ("md5sum ${BAM_PREFIX}.MateUnmapped.2.fastq.gz >${BAM_PREFIX}.MateUnmapped.2.fastq.gz.md5");
	$CODE = __LINE__; &CheckExit;
}
print LOG "md5sum ${BAM_PREFIX}.MateMapped.1.fastq.gz >${BAM_PREFIX}.MateMapped.1.fastq.gz.md5 \n";
if ($DoneUnmapped == 0) {
	system ("md5sum ${BAM_PREFIX}.MateMapped.1.fastq.gz >${BAM_PREFIX}.MateMapped.1.fastq.gz.md5");
	$CODE = __LINE__; &CheckExit;
}
print LOG "md5sum ${BAM_PREFIX}.MateMapped.2.fastq.gz >${BAM_PREFIX}.MateMapped.2.fastq.gz.md5 \n";
if ($DoneUnmapped == 0) {
	system ("md5sum ${BAM_PREFIX}.MateMapped.2.fastq.gz >${BAM_PREFIX}.MateMapped.2.fastq.gz.md5");
	$CODE = __LINE__; &CheckExit;
}
print LOG "md5sum ${BAM_PREFIX}.links.sam >${BAM_PREFIX}.links.sam.md5 \n";
if ($DoneUnmapped == 0) {
	system ("md5sum ${BAM_PREFIX}.links.sam >${BAM_PREFIX}.links.sam.md5");
	$CODE = __LINE__; &CheckExit;
}
push (@FilesToCopy, "${BAM_PREFIX}.MateUnmapped.1.fastq.gz");
push (@FilesToCopy, "${BAM_PREFIX}.MateUnmapped.1.fastq.gz.md5");
push (@FilesToCopy, "${BAM_PREFIX}.MateUnmapped.2.fastq.gz");
push (@FilesToCopy, "${BAM_PREFIX}.MateUnmapped.2.fastq.gz.md5");
push (@FilesToCopy, "${BAM_PREFIX}.MateMapped.1.fastq.gz");
push (@FilesToCopy, "${BAM_PREFIX}.MateMapped.1.fastq.gz.md5");
push (@FilesToCopy, "${BAM_PREFIX}.MateMapped.2.fastq.gz");
push (@FilesToCopy, "${BAM_PREFIX}.MateMapped.2.fastq.gz.md5");
push (@FilesToCopy, "${BAM_PREFIX}.links.sam");
push (@FilesToCopy, "${BAM_PREFIX}.links.sam.md5");

$TimeEnd = new Benchmark;
$TimeDiff = timediff($TimeEnd, $TimeStart);
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber EXTRACT UNPAIRED\tALL FILES\t", timestr($TimeDiff), "\n";
&DirectorySize;
system ("echo \"DONE Unmapped\" >DoneUnmapped");

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# UNMAPPED ONLY Skip everything after mapping and unmapped reads 
if ($UnmappedOnly == 0) { 
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

###############################################################################
# GATK SplitNCigarReads for RNAseq data
# This only needs to be run for RNAseq data

if ($Analysis eq 'rna' and $DoSplitNCigar == 1) {
	$StageNumber++;
	$TimeStart = new Benchmark;
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber GATK SplitNCigarReads\tALL FILES\t\t\n";
	print "GATK SplitNCigarReads\n";
	print LOG "# GATK SplitNCigarReads\n";
	if ($DoneSplitNCigar == 1) { print LOG "# GATK SplitNCigarReads ALREADY DONE\n"; }
}

my $SplitNCigarSem = 1;
if ($Cpu_Node >= 28 ) {	
	$SplitNCigarSem = 14;
	$Cpu_SplitNCigar = 2;	# Changed from 1 to 2 03/24/2019
}
else {
	$SplitNCigarSem = int($Cpu_Node / 2);
	$Cpu_SplitNCigar = 2;	# Changed from 1 to 2 03/24/2019
}

my $semSplitNCigar = Thread::Semaphore->new($SplitNCigarSem);
my @SplitNCigarThreads;
foreach (@SeqForIndelTargetX) {
	$semSplitNCigar->down;
	$t = threads->new(\&SplitNCigar, $_);
	push(@SplitNCigarThreads,$t);

	push(@Files2DelSplitNCigar, "${BAM_PREFIX}.${_}.SPLIT.bam");
	push(@Files2DelSplitNCigar, "${BAM_PREFIX}.${_}.SPLIT.bai");
	sleep 1;
}
foreach (@SplitNCigarThreads) { $num = $_->join; }

if ($Analysis eq 'rna' and $DoSplitNCigar == 1) {
	$TimeEnd = new Benchmark;
	$TimeDiff = timediff($TimeEnd, $TimeStart);
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber GATK SplitNCigarReads\t${BAM_PREFIX}.bam\t", timestr($TimeDiff), "\n";
	&DirectorySize;
	system ("echo \"DONE DoneSplitNCigar\" >DoneSplitNCigar");
}

=pod
04/26/2023 0.7.1 running new pipeline for RNAseq we were getting this error, primarily for the Y chr.
We sporadically see this error with WGS also. Sometimes simply rerunning the sample will get past it.

##### ERROR MESSAGE: SAM/BAM/CRAM file <...> appears to be using the wrong encoding for quality scores: 
we encountered an extremely high quality score of 69. 
Please see https://software.broadinstitute.org/gatk/documentation/article?id=6470 for more details and options related to this error.
https://gatk.broadinstitute.org/hc/en-us/articles/360035532312-Errors-about-misencoded-quality-scores

Adding -allowPotentiallyMisencodedQuals gets past this error with a test offending sample.
The problem with adding this is that it will let you get past the offending portions of the file
but later on during BQSR you cannot proceed if there are mixed QV within a file.
Therefore, we will not add this because it is an indication that something is wrong with the input data.
=cut


sub SplitNCigar {
	if ($Analysis eq 'rna' and $DoSplitNCigar == 1) {	# changed -Xmx4g to -Xmx10g 03/24/2019
		if ($_ eq "UNMAPPED") {	
			print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx10g -jar $GATK -T SplitNCigarReads -R ${RefGenome}/${ref}.fa -I ${BAM_PREFIX}.bam -L UNMAPPED_contigs.interval_list -o ${BAM_PREFIX}.UNMAPPED.SPLIT.bam -rf ReassignOneMappingQuality -RMQF 255 -RMQT 60 -U ALLOW_N_CIGAR_READS --bam_compression 0\n";
			$Stage = "$StageNumber $LI $TI GATK SplitNCigarReads UNMAPPED";
			if ($DoneSplitNCigar == 0) {
				system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx10g -jar $GATK -T SplitNCigarReads -R ${RefGenome}/${ref}.fa -I ${BAM_PREFIX}.bam -L UNMAPPED_contigs.interval_list -o ${BAM_PREFIX}.UNMAPPED.SPLIT.bam -rf ReassignOneMappingQuality -RMQF 255 -RMQT 60 -U ALLOW_N_CIGAR_READS --bam_compression 0");
				$CODE = __LINE__; &CheckExit;
			}
		}
		else {
			print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx10g -jar $GATK -T SplitNCigarReads -R ${RefGenome}/${ref}.fa -I ${BAM_PREFIX}.bam -L $_ -o ${BAM_PREFIX}.${_}.SPLIT.bam -rf ReassignOneMappingQuality -RMQF 255 -RMQT 60 -U ALLOW_N_CIGAR_READS --bam_compression 0\n";
			$Stage = "$StageNumber $LI $TI GATK SplitNCigarReads $_";
			if ($DoneSplitNCigar == 0) {
				system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx10g -jar $GATK -T SplitNCigarReads -R ${RefGenome}/${ref}.fa -I ${BAM_PREFIX}.bam -L $_ -o ${BAM_PREFIX}.${_}.SPLIT.bam -rf ReassignOneMappingQuality -RMQF 255 -RMQT 60 -U ALLOW_N_CIGAR_READS --bam_compression 0");
				$CODE = __LINE__; &CheckExit;
			}
		}
	}	
	$semSplitNCigar->up;
}

###############################################################################
# INDEL REALIGNER TARGET CREATOR
$StageNumber++;
$TimeStart = new Benchmark;
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber GATK RealignerTargetCreator\tALL FILES\t\t\n";
print "GATK RealignerTargetCreator\n";
print LOG "# GATK RealignerTargetCreator\n";
if ($DoneIndelCreator == 1) { print LOG "# GATK RealignerTargetCreator ALREADY DONE\n"; }

my $IndelTargetSem = 1;
if (int($Cpu_Node / 4) > 1 ) {
	$IndelTargetSem = int($Cpu_Node / 4);
	$Cpu_RTC = 4;
}
my $semIndelTarget = Thread::Semaphore->new($IndelTargetSem);
my @IndelTargetThreads;

foreach (@SeqForIndelTargetX) {
	$semIndelTarget->down;
	my $t = threads->new(\&IndelTarget, $_);
	push(@IndelTargetThreads,$t);
	sleep 1;
}
foreach (@IndelTargetThreads) { my $num = $_->join; }

$TimeEnd = new Benchmark;
$TimeDiff = timediff($TimeEnd, $TimeStart);
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber GATK RealignerTargetCreator\t${BAM_PREFIX}.bam\t", timestr($TimeDiff), "\n";
&DirectorySize;
system ("echo \"DONE DoneIndelCreator\" >DoneIndelCreator");

sub IndelTarget {
	#UNMAPPED
	if ($_ eq "UNMAPPED") {	
		$Stage = "$StageNumber $LI $TI GATK RealignerTargetCreator Unamapped";
		if ($Analysis eq 'rna') {
			# The input file is different if this is an RNAseq analysis because the files had to go through SplitNCigarRead
			# Changed -Xmx4g to -Xmx8g because this was failing due to not enough memory for RNAseq 03/24/2019
			print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx8g -jar $GATK -nt $Cpu_RTC -T RealignerTargetCreator -R ${RefGenome}/${ref}.fa -L UNMAPPED_contigs.interval_list -I ${BAM_PREFIX}.UNMAPPED.SPLIT.bam -o ${BAM_PREFIX}.UNMAPPED.forIndelRealigner.intervals -U ALLOW_N_CIGAR_READS \n";
			if ($DoneIndelCreator == 0) {
				system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx8g -jar $GATK -nt $Cpu_RTC -T RealignerTargetCreator -R ${RefGenome}/${ref}.fa -L UNMAPPED_contigs.interval_list -I ${BAM_PREFIX}.UNMAPPED.SPLIT.bam -o ${BAM_PREFIX}.UNMAPPED.forIndelRealigner.intervals -U ALLOW_N_CIGAR_READS ");
				$CODE = __LINE__; &CheckExit;
			}
		}
		else {
			print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx8g -jar $GATK -nt $Cpu_RTC -T RealignerTargetCreator -R ${RefGenome}/${ref}.fa -L UNMAPPED_contigs.interval_list -I ${BAM_PREFIX}.bam -o ${BAM_PREFIX}.UNMAPPED.forIndelRealigner.intervals \n";
			if ($DoneIndelCreator == 0) {
				system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx8g -jar $GATK -nt $Cpu_RTC -T RealignerTargetCreator -R ${RefGenome}/${ref}.fa -L UNMAPPED_contigs.interval_list -I ${BAM_PREFIX}.bam -o ${BAM_PREFIX}.UNMAPPED.forIndelRealigner.intervals ");
				$CODE = __LINE__; &CheckExit;
			}
		}
	}
	else {
		$Stage = "$StageNumber $LI $TI GATK RealignerTargetCreator $_";
		if ($Analysis eq 'rna') {
			# The input file is different if this is an RNAseq analysis because the files had to go through SplitNCigarReads
			print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx8g -jar $GATK -nt $Cpu_RTC -T RealignerTargetCreator -R ${RefGenome}/${ref}.fa -L $_ -I ${BAM_PREFIX}.${_}.SPLIT.bam -o ${BAM_PREFIX}.${_}.forIndelRealigner.intervals -U ALLOW_N_CIGAR_READS \n";
			if ($DoneIndelCreator == 0) {
				system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx8g -jar $GATK -nt $Cpu_RTC -T RealignerTargetCreator -R ${RefGenome}/${ref}.fa -L $_ -I ${BAM_PREFIX}.${_}.SPLIT.bam -o ${BAM_PREFIX}.${_}.forIndelRealigner.intervals -U ALLOW_N_CIGAR_READS ");
				$CODE = __LINE__; &CheckExit;
			}
		}
		else {
			print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx8g -jar $GATK -nt $Cpu_RTC -T RealignerTargetCreator -R ${RefGenome}/${ref}.fa -L $_ -I ${BAM_PREFIX}.bam -o ${BAM_PREFIX}.${_}.forIndelRealigner.intervals \n";
			if ($DoneIndelCreator == 0) {
				system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx8g -jar $GATK -nt $Cpu_RTC -T RealignerTargetCreator -R ${RefGenome}/${ref}.fa -L $_ -I ${BAM_PREFIX}.bam -o ${BAM_PREFIX}.${_}.forIndelRealigner.intervals ");
				$CODE = __LINE__; &CheckExit;
			}
		}
	}
	$semIndelTarget->up;
}

###############################################################################
# REALIGNER
# NOTE: IndelRealigner cannot be threaded with -nt or -nct !!!!!!
# Realigner was taking a long time for the unmapped contigs so we broke out the unmapped contigs to a separate subroutine.
# Modified 07/13/2018
# We run the unmapped contigs into the &IndelRealign semaphore using one slot which has a total of $Cpu_Node/2 slots
# From the 1 Unmapped slot we use the other half of the $Cpu_Node slots to run the different contig chunks in parallel.
# After the unmapped contigs are done realigning, we merge them within the single &IndelRealign slot and then return that slot for the next chr

$StageNumber++;
$TimeStart = new Benchmark;
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber GATK Realigner\tALL FILES\t\t\n";
print "GATK Realigner\n";
print LOG "# GATK Realigner\n";
if ($DoneIndelRealigner == 1) { print LOG "# GATK Realigner ALREADY DONE\n"; }

# Changed $Cpu_Realigner from 4 to 2 to allow more semaphores to run since IndelRealigner is not threaded 06/13/2018
# Need to check the stats output to see if 2 CPU is appropriate given the compression and potential increaste I/O due to more semaphores
my $IndelRealignSem = 1;
my $IndelRealignUnmappedSem = 1;
if (int($Cpu_Node / 2) > 1 ) {
	$IndelRealignSem = int($Cpu_Node / 2);
	$IndelRealignUnmappedSem = int($Cpu_Node / 8);	# new 7 & 8 semaphores work, 10 does not work
	$Cpu_Realigner = 2;
}
else {
	$IndelRealignSem = 1;
	$IndelRealignUnmappedSem = 1;
	$Cpu_Realigner = 1;
}

my $semIndelRealign = Thread::Semaphore->new($IndelRealignSem);
my @IndelRealignThreads;

# These need to go before the &IndelRealign semaphore so they are available in that subroutine
$uc = ();							# Iterator for &IndelRealignUnmapped
$semIndelRealignUnmapped = ();		# Counter for &IndelRealignUnmapped
@IndelRealignThreadsUnmapped = ();	# Array for &IndelRealignUnmapped
$u = (); 							# Track threads in &IndelRealignUnmapped
$num1 = ();							# Track threads in &IndelRealignUnmapped

$BAM_SUFFIX = "realigned";
foreach (@SeqForIndelTargetX) {
		$semIndelRealign->down;
		$t = threads->new(\&IndelRealign, $_);
		push(@IndelRealignThreads,$t);
		push(@Files2DelRealigner, "${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bam");
		push(@Files2DelRealigner, "${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bai");
		sleep 1;
}
foreach (@IndelRealignThreads) { my $num = $_->join; }

$TimeEnd = new Benchmark;
$TimeDiff = timediff($TimeEnd, $TimeStart);
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber GATK Realigner\t${BAM_PREFIX}.bam\t", timestr($TimeDiff), "\n";
&DirectorySize;
system ("echo \"DONE DoneIndelRealigner\" >DoneIndelRealigner");

sub IndelRealign {
	# NOTE: IndelRealigner cannot be threaded with -nt or -nct !!!!!!
	# We use one semaphor to run all the chunks of UNMAPPED. After IndelRealigner is done we need to merge BAM for the Unmapped chunks into a single ${BAM_PREFIX}.UNMAPPED.realigned.bam
	# Removed --bam_compression 0 06/13/2018 

	# 04/20/2021 Added the $JavaMem here and standardized all of the -Xmx${JavaMem}g
	# Some chromosomes were running out of memory and failing because they were a mix of old 4g and newer 8g.
	# Since we're only ever running at most 28 semaphores, setting $JavaMem = 10 would use 280G on a BioCompute node and 240G on a hpc6 node
	$JavaMem = 10;
	if ($_ eq "UNMAPPED") {
		$semIndelRealignUnmapped = Thread::Semaphore->new($IndelRealignUnmappedSem); # new
		$uc = 1;			
		while ($uc <= $NumUnmappedHClists) {
			$semIndelRealignUnmapped->down;
			$u = threads->new(\&IndelRealignUnmapped, $_);
			push(@IndelRealignThreadsUnmapped,$u);
			push(@Files2DelRealigner, "${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bam");
			push(@Files2DelRealigner, "${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bai");
			sleep 1;
			$uc++;

		}
		foreach (@IndelRealignThreadsUnmapped) { $num1 = $_->join; }

		print LOG "# Realigner Completed doing Samtools Merge UNMAPPED\n";
		##############
		# Merge UNMAPPED BAM back into single ${BAM_PREFIX}.UNMAPPED.${BAM_SUFFIX}.bam
		$uc = 1;			
		open TMP, ">${BAM_PREFIX}_UNMAPPED_MergeRealignedFiles.list";
		while ($uc <= $NumUnmappedHClists) {
			print TMP "${BAM_PREFIX}.UNMAPPED${uc}.${BAM_SUFFIX}.bam\n";
			#push(@Files2DelRealigner, "${BAM_PREFIX}.UNMAPPED${uc}.${BAM_SUFFIX}.bam");
			$uc++;
		}
		close TMP;

		# Changed back to 10 01/04/2019 because 20 was too much
		if (int($Cpu_Node / 10) > 1 ) { $Cpu_Samtools = 10; }
		print LOG "$Samtools merge -\@ $Cpu_Samtools -f -c -p -b ${BAM_PREFIX}_UNMAPPED_MergeRealignedFiles.list ${BAM_PREFIX}.UNMAPPED.${BAM_SUFFIX}.bam\n";
		$Stage = "$StageNumber $LI $TI SAMTOOLS MERGE INDELREALIGNER UNMAPPED";
		if ($DoneIndelRealigner == 0) {
			system ("$Samtools merge -\@ $Cpu_Samtools -f -c -p -b ${BAM_PREFIX}_UNMAPPED_MergeRealignedFiles.list ${BAM_PREFIX}.UNMAPPED.${BAM_SUFFIX}.bam");
			$CODE = __LINE__; &CheckExit;
		}
		print LOG "# DONE doing Samtools Merge UNMAPPED\n";
		#
		##############
	}

	# 04/20/2021 Some samples were failing with error 
	##### ERROR MESSAGE: If the maximum allowable reads in memory is too small, 
	##### it may cause reads to be written out of order when trying to write the BAM; 
	##### please see the --maxReadsInMemory argument for details.
	# The default --maxReadsInMemory = 150000
	# Changing this to --maxReadsInMemory = 300000 solved the problem for the 199961 case so we'll add this to all.
	elsif ($_ ne "UNMAPPED") {
		if ($Analysis eq 'rna') {
			if ($_ eq 'MT') { $JavaMem = 20; }	# IndelRealignment was running out of MEM for RNAseq for the MT
			#else { $JavaMem = 8; }	# changed from 4 to 8 because some RNAseq was running out of mem 03/27/2019
			print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx${JavaMem}g -jar $GATK -R ${RefGenome}/${ref}.fa -I ${BAM_PREFIX}.${_}.SPLIT.bam -T IndelRealigner -targetIntervals ${BAM_PREFIX}.${_}.forIndelRealigner.intervals -L $_ -o ${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bam -U ALLOW_N_CIGAR_READS --maxReadsInMemory 300000 \n";
			$Stage = "$StageNumber $LI $TI GATK Realigner $_";
			if ($DoneIndelRealigner == 0) {
				system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx${JavaMem}g -jar $GATK -R ${RefGenome}/${ref}.fa -I ${BAM_PREFIX}.${_}.SPLIT.bam -T IndelRealigner -targetIntervals ${BAM_PREFIX}.${_}.forIndelRealigner.intervals -L $_ -o ${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bam -U ALLOW_N_CIGAR_READS --maxReadsInMemory 300000 ");
				$CODE = __LINE__; &CheckExit;
			}
		}
		else {
			print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx${JavaMem}g -jar $GATK -R ${RefGenome}/${ref}.fa -I ${BAM_PREFIX}.bam -T IndelRealigner -targetIntervals ${BAM_PREFIX}.${_}.forIndelRealigner.intervals -L $_ -o ${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bam --maxReadsInMemory 300000 \n";
			$Stage = "$StageNumber $LI $TI GATK Realigner $_";
			if ($DoneIndelRealigner == 0) {
				system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx${JavaMem}g -jar $GATK -R ${RefGenome}/${ref}.fa -I ${BAM_PREFIX}.bam -T IndelRealigner -targetIntervals ${BAM_PREFIX}.${_}.forIndelRealigner.intervals -L $_ -o ${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bam --maxReadsInMemory 300000 ");
				$CODE = __LINE__; &CheckExit;
			}
		}
	}	
	$semIndelRealign->up;
}	

sub IndelRealignUnmapped {
	if ($Analysis eq 'rna') {
		print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx${JavaMem}g -jar $GATK -R ${RefGenome}/${ref}.fa -I ${BAM_PREFIX}.UNMAPPED.SPLIT.bam -T IndelRealigner -targetIntervals ${BAM_PREFIX}.UNMAPPED.forIndelRealigner.intervals -L UNMAPPED_contigs${uc}.interval_list -o ${BAM_PREFIX}.UNMAPPED${uc}.${BAM_SUFFIX}.bam -U ALLOW_N_CIGAR_READS --maxReadsInMemory 300000 \n";
		if ($DoneIndelRealigner == 0) {
			system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx${JavaMem}g -jar $GATK -R ${RefGenome}/${ref}.fa -I ${BAM_PREFIX}.UNMAPPED.SPLIT.bam -T IndelRealigner -targetIntervals ${BAM_PREFIX}.UNMAPPED.forIndelRealigner.intervals -L UNMAPPED_contigs${uc}.interval_list -o ${BAM_PREFIX}.UNMAPPED${uc}.${BAM_SUFFIX}.bam -U ALLOW_N_CIGAR_READS --maxReadsInMemory 300000 ");
		}
	}
	else {
		print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx${JavaMem}g -jar $GATK -R ${RefGenome}/${ref}.fa -I ${BAM_PREFIX}.bam -T IndelRealigner -targetIntervals ${BAM_PREFIX}.UNMAPPED.forIndelRealigner.intervals -L UNMAPPED_contigs${uc}.interval_list -o ${BAM_PREFIX}.UNMAPPED${uc}.${BAM_SUFFIX}.bam --maxReadsInMemory 300000 \n";
		if ($DoneIndelRealigner == 0) {
			system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx${JavaMem}g -jar $GATK -R ${RefGenome}/${ref}.fa -I ${BAM_PREFIX}.bam -T IndelRealigner -targetIntervals ${BAM_PREFIX}.UNMAPPED.forIndelRealigner.intervals -L UNMAPPED_contigs${uc}.interval_list -o ${BAM_PREFIX}.UNMAPPED${uc}.${BAM_SUFFIX}.bam --maxReadsInMemory 300000 ");
		}
	}
	$Stage = "$StageNumber $LI $TI GATK Realigner UNMAPPED";
	$CODE = __LINE__; &CheckExit;
	$semIndelRealignUnmapped->up;
}

###############################################################################
# MERGE REALIGNED FILES
# Write list of realigned bam files to merge
open TMP, ">${BAM_PREFIX}_MergeRealignedFiles.list";
foreach (@SeqForIndelTarget) {
	print TMP "${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bam\n";
	push (@MergeRealignedFiles, "INPUT=${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bam ");
}
print TMP "${BAM_PREFIX}.UNMAPPED.${BAM_SUFFIX}.bam\n";
push (@MergeRealignedFiles, "INPUT=${BAM_PREFIX}.UNMAPPED.${BAM_SUFFIX}.bam ");
close TMP;

# Changed back to 10 01/04/2019 20 was too much and not used efficiently
# Changed from 10 to 8 04/26/2023 watching this it was only using ~7
if (int($Cpu_Node / 8) > 1 ) { $Cpu_Samtools = 8; }

$StageNumber++;
$TimeStart = new Benchmark;
print "SAMTOOLS MERGE REALIGNED\n";
print LOG "# SAMTOOLS MERGE REALIGNED\n";
if ($DoneMergeRealigned == 1) { print LOG "# SAMTOOLS MERGE REALIGNED ALREADY DONE\n"; }
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber SAMTOOLS MERGE\tREALIGNED FILES\t\t\n";

# We can use the -c flag for samtools merge here because all of the individual Chr bam files have the same read groups present
# 05/23/2018 Added -p option to Combine PG tags with colliding IDs rather than adding a suffix to differentiate them
# 06/10/2018 Removed the -u flag for uncompressed
print LOG "$Samtools merge -\@ $Cpu_Samtools -f -c -p -b ${BAM_PREFIX}_MergeRealignedFiles.list ${BAM_PREFIX}.${BAM_SUFFIX}.bam\n";
$Stage = "$StageNumber $LI $TI SAMTOOLS MERGE";
if ($DoneMergeRealigned == 0) {
	system ("$Samtools merge -\@ $Cpu_Samtools -f -c -p -b ${BAM_PREFIX}_MergeRealignedFiles.list ${BAM_PREFIX}.${BAM_SUFFIX}.bam");
	$CODE = __LINE__; &CheckExit;
}
$TimeEnd = new Benchmark;
$TimeDiff = timediff($TimeEnd, $TimeStart);
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber SAMTOOLS MERGE\t${BAM_PREFIX}.${BAM_SUFFIX}.bam\t", timestr($TimeDiff), "\n";
&DirectorySize;
system ("echo \"DONE DoneMergeRealigned\" >DoneMergeRealigned");

###############################################################################
# INDEX REALIGNED BAM
$StageNumber++;
$TimeStart = new Benchmark;
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber SAMTOOLS INDEX\tALL FILES\t\t\n";
print LOG "# SAMTOOLS INDEX REALIGNED BAM\n";
if ($DoneIndexRealigned == 1) { print LOG "# SAMTOOLS INDEX REALIGNED BAM ALREADY DONE\n"; }
print LOG "$Samtools index -\@ 8 ${BAM_PREFIX}.${BAM_SUFFIX}.bam\n";
print LOG "md5sum ${BAM_PREFIX}.${BAM_SUFFIX}.bam >${BAM_PREFIX}.${BAM_SUFFIX}.bam.md5\n";
print LOG "md5sum ${BAM_PREFIX}.${BAM_SUFFIX}.bam.bai >${BAM_PREFIX}.${BAM_SUFFIX}.bam.bai.md5\n";
$Stage = "$StageNumber $LI $TI SAMTOOLS INDEX";
if ($DoneIndexRealigned == 0) {
	system ("$Samtools index -\@ 8 ${BAM_PREFIX}.${BAM_SUFFIX}.bam");
	$CODE = __LINE__; &CheckExit;
	system ("md5sum ${BAM_PREFIX}.${BAM_SUFFIX}.bam >${BAM_PREFIX}.${BAM_SUFFIX}.bam.md5");
	$CODE = __LINE__; &CheckExit;
	system ("md5sum ${BAM_PREFIX}.${BAM_SUFFIX}.bam.bai >${BAM_PREFIX}.${BAM_SUFFIX}.bam.bai.md5");
	$CODE = __LINE__; &CheckExit;
}

# Added 01/24/2021 v0.6.1
# When $DoBQSR was 0 we were not adding the ${BAM_PREFIX}.realigned.bam to the @FilesToCopy
if ($DoBQSR == 0) {
	if {$DoBam2Cram == 0) {
		push (@FilesToCopy, "${BAM_PREFIX}.${BAM_SUFFIX}.bam");
		push (@FilesToCopy, "${BAM_PREFIX}.${BAM_SUFFIX}.bam.md5");
		push (@FilesToCopy, "${BAM_PREFIX}.${BAM_SUFFIX}.bam.bai");
		push (@FilesToCopy, "${BAM_PREFIX}.${BAM_SUFFIX}.bam.bai.md5");
	}
	else {
		push (@FilesToCopy, "${BAM_PREFIX}.${BAM_SUFFIX}.cram");
		push (@FilesToCopy, "${BAM_PREFIX}.${BAM_SUFFIX}.cram.md5");
		push (@FilesToCopy, "${BAM_PREFIX}.${BAM_SUFFIX}.cram.crai");
		push (@FilesToCopy, "${BAM_PREFIX}.${BAM_SUFFIX}.cram.crai.md5");
	}
}


$TimeEnd = new Benchmark;
$TimeDiff = timediff($TimeEnd, $TimeStart);
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber SAMTOOLS INDEX\t${BAM_PREFIX}.${BAM_SUFFIX}.bam\t", timestr($TimeDiff), "\n";
&DirectorySize;
system ("echo \"DONE IndexRealigned\" >DoneIndexRealigned");

###############################################################################
# Now that Realigner is done it's safe to delete the output files from Mark Dups
print "DELETING @Files2DelMarkDups\n";
print LOG "# DELETING MARKDUPS files\n";
foreach (@Files2DelMarkDups) {
	print LOG "rm $_\n";
	system ("rm $_");
}

if ($DoBQSR == 1) {
	###############################################################################
	# Now that Realigner is done it's safe to delete the output files from Realigner
	print "DELETING @Files2DelRealigner\n";
	print LOG "# DELETING REALIGNER FILES\n";
	foreach (@Files2DelRealigner) {
		print LOG "rm $_\n";
		system ("rm $_");
	}
	print LOG "rm ${BAM_PREFIX}.UNMAPPED*.${BAM_SUFFIX}.bam\n";
	system ("rm ${BAM_PREFIX}.UNMAPPED*.${BAM_SUFFIX}.bam");
	###############################################################################
	#BASE QUALITY SCORE RECALIBRATION
	$StageNumber++;
	$TimeStart = new Benchmark;
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber GATK BaseRecalibrator\tALL FILES\t\t\n";
	print LOG "# GATK BaseRecalibrator\n";
	if ($DoneBQSR == 1) { print LOG "# BQSR ALREADY DONE\n"; }

	# File "${snp_dir}/BQSR_${BqsrSize}MB_target.interval_list" contains the interval list to use for the recalibration.
	# This file must be created for each new reference genome genome
	# Set the size of the recalibration target to use based on the size of the BAM file
	# Added 02/23/2018, Changed new thresholds 06/10/2018

	# Building the BQSR model using the entire genome is optimal but takes a LONG time.
	# We have tested the results of using smaller subsets of the genome and found that you can achieve nearly identical results.
	# It is dependent on the total amount of data fed into building the model. So for higher coverave genomes we restrict
	# the portion of the genome used to be 5, 10, 20 MB from each of the chromosomes and call these the 'target' regions.
	# After BQSR is done we then build the 2nd model using a *different* 'check' set of intervals to evaluate how well we did. 
	# By doing this, we are evaluating how well we did on positions that were not seen when building the firt model.
	# By doing smaller regions for higher coverage genomes we significantly reduce the time for this stage.

	if ($DoneBQSR == 0) {
		$BAMFileSize = `du "${BAM_PREFIX}.${BAM_SUFFIX}.bam" | cut -f1`;
		chomp $BAMFileSize;	
		print "$BAMFileSize\t${BAM_PREFIX}.${BAM_SUFFIX}.bam\n";	
		# If the BQSR is set to ALL on the command line do not change the target interval size
		if (uc $BqsrSize ne "ALL") {
			if ($BAMFileSize < 10000000) {			# Low coverage we do the entire genome Added 09/27/2019
				$BqsrSize = "ALL";	
			}
			if ($BAMFileSize < 35000000) {			# 35GB BAM is < 10X mammalian coverage so use 20 Mb from each chr
				$BqsrSize = 20;	
			}
			elsif ($BAMFileSize < 70000000) {		# 70GB BAM is < 20X mammalian coverage so use 10 Mb from each chr
				$BqsrSize = 10;	
			}
			else { $BqsrSize = 5; }					# >70GB BAM is > 20X mammalian coverage so use 5 Mb from each chr
		}
	}
	# If BQSR was already completed then the ${BAM_PREFIX}.${BAM_SUFFIX}.bam has likely already been deleted
	# Therefore the $BqsrSize variable will be either the default or what was specified on the command line
	# which many not reflect the actual size used when it was originally run.
	if (int($Cpu_Node / 24) >= 1 ) { $Cpu_BQSR = 24; }

#	--use-original-qualities not implemented in 3.8 so we don't include it here
	print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx20g -jar $GATK -nct $Cpu_BQSR -T BaseRecalibrator -R ${RefGenome}/${ref}.fa -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -L ${RefSNP}/${snp_dir}/BQSR_${BqsrSize}MB_target.interval_list -knownSites ${RefSNP}/${snp_dir}/${KnownSites} --bqsrBAQGapOpenPenalty $bqsrBAQGOP --deletions_default_quality $indelQUAL --insertions_default_quality $indelQUAL -o ${BAM_PREFIX}.recalibration_report.grp -U ALLOW_N_CIGAR_READS --quantizing_levels 24 \n";
	push (@FilesToCopy, "${BAM_PREFIX}.recalibration_report.grp");
	$Stage = "$StageNumber $LI $TI GATK BaseRecalibrator";
	if ($DoneBQSR == 0) {
		system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx20g -jar $GATK -nct $Cpu_BQSR -T BaseRecalibrator -R ${RefGenome}/${ref}.fa -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -L ${RefSNP}/${snp_dir}/BQSR_${BqsrSize}MB_target.interval_list -knownSites ${RefSNP}/${snp_dir}/${KnownSites} --bqsrBAQGapOpenPenalty $bqsrBAQGOP --deletions_default_quality $indelQUAL --insertions_default_quality $indelQUAL -o ${BAM_PREFIX}.recalibration_report.grp -U ALLOW_N_CIGAR_READS --quantizing_levels 24 ");
		$CODE = __LINE__; &CheckExit;
	}
	########
	# BQSR report
#	print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:ParallelGCThreads=2 -Xmx10g -jar $GATK -T AnalyzeCovariates -R ${RefGenome}/${ref}.fa -BQSR ${BAM_PREFIX}.recalibration_report.grp -plots ${BAM_PREFIX}.BQSR.pdf -U ALLOW_N_CIGAR_READS \n";
	# Changed this to use GATK4 due to issues with updating R and the old BQSR.R script in the jar would not work
	print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx10g -jar $GATK4 AnalyzeCovariates -bqsr ${BAM_PREFIX}.recalibration_report.grp -plots ${BAM_PREFIX}.BQSR.pdf \n";
	push (@FilesToCopy, "${BAM_PREFIX}.BQSR.pdf");
	$Stage = "$StageNumber $LI $TI GATK BaseRecalibrator Report";
	if ($DoneBQSR == 0) {
#		system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:ParallelGCThreads=2 -Xmx10g -jar $GATK -T AnalyzeCovariates -R ${RefGenome}/${ref}.fa -BQSR ${BAM_PREFIX}.recalibration_report.grp -plots ${BAM_PREFIX}.BQSR.pdf -U ALLOW_N_CIGAR_READS");
		system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx10g -jar $GATK4 AnalyzeCovariates -bqsr ${BAM_PREFIX}.recalibration_report.grp -plots ${BAM_PREFIX}.BQSR.pdf");
		$CODE = __LINE__; &CheckExit;
	}

	$TimeEnd = new Benchmark;
	$TimeDiff = timediff($TimeEnd, $TimeStart);
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber GATK BaseRecalibrator\t${BAM_PREFIX}.bam\t", timestr($TimeDiff), "\n";
	&DirectorySize;

	########
	# BQSR PrintReads
	# Recalibrate creating new bam
	$StageNumber++;
	$TimeStart = new Benchmark;
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber GATK BQSR PrintReads\tALL FILES\t\t\n";
	print "BEGIN GATK BQSR PrintReads\n";
	print LOG "# GATK BQSR PrintReads\n";

	my $BQSRprintSem = 1;
	if (int($Cpu_Node / 4) > 1 ) {
		$BQSRprintSem = int($Cpu_Node / 4);
		$Cpu_PR = 5;
	}

	# These need to go before the &PrintReads semaphore so they are available in that subroutine
	$uc = ();							# Iterator for &IndelRealignUnmapped
	$semPrintReadsUnmapped = ();		# Counter for &IndelRealignUnmapped
	@PrintReadsThreadsUnmapped = ();	# Array for &IndelRealignUnmapped
	$u = (); 							# Track threads in &IndelRealignUnmapped
	$num1 = ();							# Track threads in &IndelRealignUnmapped

	# This is the main parameter that should be tuned to determine how long the unmapped reads take
	my $PrintReadsUnmappedSem = 5; 

	my $semBQSRprint = Thread::Semaphore->new($BQSRprintSem);
	my @BQSRprintThreads;
	foreach (@SeqForIndelTargetX) {
		$semBQSRprint->down;
		my $t = threads->new(\&BQSRprint, $_);
		push(@BQSRprintThreads,$t);
		sleep 1;
	}
	foreach (@BQSRprintThreads) { $num = $_->join; }

	sub BQSRprint {
		if ($_ eq "UNMAPPED") {
			$semPrintReadsUnmapped = Thread::Semaphore->new($PrintReadsUnmappedSem); # new
			$uc = 1;			
			while ($uc <= $NumUnmappedHClists) {
				$semPrintReadsUnmapped->down;
				$u = threads->new(\&PrintReadsUnmapped, $_);
				push(@PrintReadsThreadsUnmapped,$u);
				sleep 1;
				$uc++;
			}
			foreach (@PrintReadsThreadsUnmapped) { $num1 = $_->join; }

			print LOG "# PrintReads Completed doing Samtools Merge UNMAPPED\n";
			##############
			# Merge UNMAPPED BAM back into single ${BAM_PREFIX}.UNMAPPED.${BAM_SUFFIX}.recalibrated.bam
			$uc = 1;			
			open TMP, ">${BAM_PREFIX}_UNMAPPED_MergePrintReadsFiles.list";
			while ($uc <= $NumUnmappedHClists) {
				print TMP "${BAM_PREFIX}.UNMAPPED${uc}.${BAM_SUFFIX}.recalibrated.bam\n";
				#push(@Files2DelRealigner, "${BAM_PREFIX}.UNMAPPED${uc}.${BAM_SUFFIX}.recalibrated.bam");
				$uc++;
			}
			close TMP;

			if (int($Cpu_Node / 10) > 1 ) { $Cpu_Samtools = 10; }
			print LOG "$Samtools merge -\@ $Cpu_Samtools -f -c -p -b ${BAM_PREFIX}_UNMAPPED_MergePrintReadsFiles.list ${BAM_PREFIX}.UNMAPPED.${BAM_SUFFIX}.recalibrated.bam\n";
			$Stage = "$StageNumber $LI $TI SAMTOOLS MERGE PRINTREADS UNMAPPED";
			if ($DoneBQSR == 0) {
				system ("$Samtools merge -\@ $Cpu_Samtools -f -c -p -b ${BAM_PREFIX}_UNMAPPED_MergePrintReadsFiles.list ${BAM_PREFIX}.UNMAPPED.${BAM_SUFFIX}.recalibrated.bam");
				$CODE = __LINE__; &CheckExit;
			}
			print LOG "# DONE doing Samtools Merge UNMAPPED\n";
			#
			##############
		}
		else {
			# 05/24/2021 Increased java mem from 8G to 12G because a sample (341558) was failing here due to not enough memory
			# This appears to also run a bit faster with more memory
			print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx12g -jar $GATK -nct $Cpu_PR -T PrintReads -R ${RefGenome}/${ref}.fa -L $_ -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -BQSR ${BAM_PREFIX}.recalibration_report.grp -o ${BAM_PREFIX}.${_}.${BAM_SUFFIX}.recalibrated.bam -U ALLOW_N_CIGAR_READS \n";
			$Stage = "$StageNumber $LI $TI GATK BQSR PrintReads $_";
			if ($DoneBQSR == 0) {
				system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx12g -jar $GATK -nct $Cpu_PR -T PrintReads -R ${RefGenome}/${ref}.fa -L $_ -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -BQSR ${BAM_PREFIX}.recalibration_report.grp -o ${BAM_PREFIX}.${_}.${BAM_SUFFIX}.recalibrated.bam -U ALLOW_N_CIGAR_READS ");
				$CODE = __LINE__; &CheckExit;
			}
		}	
		$semBQSRprint->up;
	}

	sub PrintReadsUnmapped {
		print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx12g -jar $GATK -nct $Cpu_PR -T PrintReads -R ${RefGenome}/${ref}.fa -L UNMAPPED_contigs${uc}.interval_list -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -BQSR ${BAM_PREFIX}.recalibration_report.grp -o ${BAM_PREFIX}.UNMAPPED${uc}.${BAM_SUFFIX}.recalibrated.bam -U ALLOW_N_CIGAR_READS \n";
		$Stage = "$StageNumber $LI $TI GATK BQSR PrintReads UNMAPPED";
		if ($DoneBQSR == 0) {
			system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx12g -jar $GATK -nct $Cpu_PR -T PrintReads -R ${RefGenome}/${ref}.fa -L UNMAPPED_contigs${uc}.interval_list -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -BQSR ${BAM_PREFIX}.recalibration_report.grp -o ${BAM_PREFIX}.UNMAPPED${uc}.${BAM_SUFFIX}.recalibrated.bam -U ALLOW_N_CIGAR_READS ");
			$CODE = __LINE__; &CheckExit;
		}
		$semPrintReadsUnmapped->up;
	}
# <<<<<< New code
##########################

	# Moved from 2296 10/01/2019
	if ($DeleteResults == 1) {
		print LOG "rm ${BAM_PREFIX}.realigned.bam\n";
		system ("rm ${BAM_PREFIX}.realigned.bam");
	}

	$TimeEnd = new Benchmark;
	$TimeDiff = timediff($TimeEnd, $TimeStart);
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber GATK BQSR PrintReads\t${BAM_PREFIX}.${BAM_SUFFIX}.bam\t", timestr($TimeDiff), "\n";
	&DirectorySize;
	system ("echo \"DONE BQSR\" >DoneBQSR");

	###############################################################################
	# MERGE recalibrated BAMS
	# Write list of realigned recalibrated bam files to merge

#	$BAM_SUFFIX = "realigned.recalibrated";
#	This broke when the $BAM_SUFFIX upstream is changed to "realigned.recalibrated' in order to start at the 
#	previously recalibrated bam. Need to rethink this.
#	At thsi point, the $BAM_SUFFIX could be 'realigned' or 'realigned.recalibrated'
#	If starting with 'realigned.recalibrated' then the reprocessed individual files will be ${BAM_PREFIX}.${_}.realigned.recalibrated.recalibrated.bam
#	If starting with 'realigned' then the reprocessed individual files will be ${BAM_PREFIX}.${_}.realigned.bam
	$BAM_SUFFIX = "${BAM_SUFFIX}.recalibrated"; # Added 09/26/2019

	open TMP, ">${BAM_PREFIX}_MergeRealignedRecalibratedFiles.list";
	foreach (@SeqForIndelTarget) {
		print TMP "${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bam\n";
		push (@Files2DelRecalibrated,"${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bam");
		push (@Files2DelRecalibrated,"${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bai");
		push (@MergeRealignedRecalibratedFiles, "INPUT=${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bam ");
	}
	print TMP "${BAM_PREFIX}.UNMAPPED.${BAM_SUFFIX}.bam\n";
	push (@MergeRealignedRecalibratedFiles, "INPUT=${BAM_PREFIX}.UNMAPPED.${BAM_SUFFIX}.bam ");
	close TMP;

	$StageNumber++;
	$TimeStart = new Benchmark;
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber SAMTOOLS MERGE\tRECALIBRATED FILES\t\t\n";
	print LOG "# SAMTOOLS MERGE RECALIBRATED FILES\n";
	print "\nSAMTOOLS MERGE REALIGNED RECALIBRATED \n";
	if ($DoneMergeRecalibrated == 1) { print LOG "# SAMTOOLS MERGE RECALIBRATED ALREADY DONE\n"; }

	# Changed back to 10 01/04/2019, 10 threads is still probably too many based on watching top
	if (int($Cpu_Node / 10) > 1 ) { $Cpu_Samtools = 10; }

	# COMPRESS FILE HERE BECAUSE IT'S THE LAST STEP AND THE FILE WE KEEP 
	# We can use the -c flag for samtools merge here because all of the Chr bam files have the same read groups present
	# 05/23/2018 Added -p option to Combine PG tags with colliding IDs rather than adding a suffix to differentiate them
	# 06/08/2019 Added -l 9 highest compression 
#	push (@FilesToCopy, "${BAM_PREFIX}.${BAM_SUFFIX}.bam");
#	Remove the $BAM_SUFFIX from all parts for this code block 09/26/2019
#	Specify $BAM_SUFFIX as 'realigned.recalibrated' from all parts for this code block 09/26/2019
	$BAM_SUFFIX = "realigned.recalibrated"; 

	if ($DoBam2Cram == 0) { push (@FilesToCopy, "${BAM_PREFIX}.${BAM_SUFFIX}.bam"); }

	# 04/23/2024 For simplicity now, we will just merge as normal and then convert the bam to cram
	# at the end before we copy. This way we don't have to change any of the code that relies on bam files.
	print LOG "$Samtools merge -\@ $Cpu_Samtools -l 9 -f -c -p -b ${BAM_PREFIX}_MergeRealignedRecalibratedFiles.list ${BAM_PREFIX}.$BAM_SUFFIX.bam\n";
	$Stage = "$StageNumber $LI $TI SAMTOOLS MERGE";
	if ($DoneMergeRecalibrated == 0) {
		system ("$Samtools merge -\@ $Cpu_Samtools -l 9 -f -c -p -b ${BAM_PREFIX}_MergeRealignedRecalibratedFiles.list ${BAM_PREFIX}.$BAM_SUFFIX.bam");
		$CODE = __LINE__; &CheckExit;
	}

	if ($DoBam2Cram == 0) {
		print "GENERATING MD5 for ${BAM_PREFIX}.$BAM_SUFFIX.bam\n";
		push (@FilesToCopy, "${BAM_PREFIX}.${BAM_SUFFIX}.bam.md5");
		$Stage = "$StageNumber $LI $TI SAMTOOLS MERGE md5sum ${BAM_PREFIX}.$BAM_SUFFIX.bam";
		if ($DoneMergeRecalibrated == 0) {
			system ("md5sum ${BAM_PREFIX}.$BAM_SUFFIX.bam >${BAM_PREFIX}.$BAM_SUFFIX.bam.md5");
			$CODE = __LINE__; &CheckExit;
		}
	}

	#####
	# Capture the read groups in the BAM file
	# samtools view -H myfile.bam | grep '^@RG' Will show the ReadGroups from the indicated BAM
	print LOG "$Samtools view -H ${BAM_PREFIX}.$BAM_SUFFIX.bam | grep \'^\@RG\' \>${BAM_PREFIX}.RG;\n";
	if ($DoneMergeRecalibrated == 0) {
		system ("$Samtools view -H ${BAM_PREFIX}.$BAM_SUFFIX.bam | grep \'^\@RG\' \>${BAM_PREFIX}.RG");
		$CODE = __LINE__; &CheckExit;
	}
	push (@FilesToCopy, "${BAM_PREFIX}.RG");

	$TimeEnd = new Benchmark;
	$TimeDiff = timediff($TimeEnd, $TimeStart);
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber SAMTOOLS MERGE\t${BAM_PREFIX}.$BAM_SUFFIX.bam\t", timestr($TimeDiff), "\n";
	&DirectorySize;
	system ("echo \"DONE MergeRecalibrated\" >DoneMergeRecalibrated");

	###############################################################################
	# Now that Recalibration is done it's safe to delete the individual output files from Recalibrator
	# Moved from 2289 10/01/2019
	print "DELETING @Files2DelRecalibrated\n";
	print LOG "# DELETING RECALIBRATOR FILES\n";
	foreach (@Files2DelRecalibrated) {
		print LOG "rm $_\n";
		system ("rm $_");
	}

	###############################################################################
	#INDEX REALIGNED RECALIBRATED BAM
	$StageNumber++;
	$TimeStart = new Benchmark;
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber SAMTOOLS INDEX\tALL FILES\t\t\n";
	print LOG "# SAMTOOLS INDEX RECALIBRATED FILES\n";
	if ($DoneIndexRecalibrated == 1) { print LOG "# SAMTOOLS INDEX RECALIBRATED ALREADY DONE\n"; }
#	Specify $BAM_SUFFIX as 'realigned.recalibrated' from all parts for this code block 09/26/2019
	$BAM_SUFFIX = "realigned.recalibrated"; 
	print "SAMTOOLS INDEX BAM ${BAM_PREFIX}.${BAM_SUFFIX}.bam\n";
	print LOG "$Samtools index -\@ 4 ${BAM_PREFIX}.${BAM_SUFFIX}.bam\n";

	if ($DoBam2Cram == 0) {
		push (@FilesToCopy, "${BAM_PREFIX}.${BAM_SUFFIX}.bam.bai");
		push (@FilesToCopy, "${BAM_PREFIX}.${BAM_SUFFIX}.bam.bai.md5");
	}

	$Stage = "$StageNumber $LI $TI SAMTOOLS INDEX";
	if ($DoneIndexRecalibrated == 0) {
		system ("$Samtools index -\@ 4 ${BAM_PREFIX}.${BAM_SUFFIX}.bam");
		$CODE = __LINE__; &CheckExit;
	}

	if ($DoBam2Cram == 0) {
		$Stage = "$StageNumber $LI $TI SAMTOOLS INDEX md5sum ${BAM_PREFIX}.${BAM_SUFFIX}.bam.bai";
		print LOG "md5sum ${BAM_PREFIX}.${BAM_SUFFIX}.bam.bai >${BAM_PREFIX}.${BAM_SUFFIX}.bam.bai.md5\n";
		if ($DoneIndexRecalibrated == 0) {
			system ("md5sum ${BAM_PREFIX}.${BAM_SUFFIX}.bam.bai >${BAM_PREFIX}.${BAM_SUFFIX}.bam.bai.md5");
			$CODE = __LINE__; &CheckExit;
		}
	}
	$TimeEnd = new Benchmark;
	$TimeDiff = timediff($TimeEnd, $TimeStart);
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber SAMTOOLS INDEX\t${BAM_PREFIX}.${BAM_SUFFIX}.bam\t", timestr($TimeDiff), "\n";
	&DirectorySize;
	system ("echo \"DONE IndexRecalibrated\" >DoneIndexRecalibrated");

	###############################################################################
	# BASE QUALITY SCORE RECALIBRATION 2 & 3
	# Rerun the recalibrator on the recalibrated bam to produce a before/after figure
	# For the second pass we use a different set of coordinates from the *_target.interval_list 
	$StageNumber++;
	$TimeStart = new Benchmark;
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber GATK BaseRecalibrator2\tALL FILES\t\t\n";
	print LOG "# GATK BaseRecalibrator2\n";
	if ($DoneBQSRreports == 1) { print LOG "# GATK BaseRecalibrator2 ALREADY DONE\n"; }

#	if (int($Cpu_Node / 32) >= 1 ) { $Cpu_BQSR = 32; } # changed 07/13/2018
	if (int($Cpu_Node / 24) >= 1 ) { $Cpu_BQSR = 24; } # 09/25/2019 changed back to 24 in order to work on more of the Lewis Partitions

	# 5Mb or 10Mb from all autosomes + X
	# File "${snp_dir}/BQSR_${BqsrSize}MB_check.interval_list" contains the interval list to use for the recalibration.
	# This file must be created for each new reference genome genome

#	Specify $BAM_SUFFIX as 'realigned.recalibrated' from all parts for this code block 09/26/2019
	$BAM_SUFFIX = "realigned.recalibrated"; 

#	--use-original-qualities not implemented in 3.8
	print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx20g -jar $GATK -nct $Cpu_BQSR -T BaseRecalibrator -R ${RefGenome}/${ref}.fa -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -L ${RefSNP}/${snp_dir}/BQSR_${BqsrSize}MB_check.interval_list -knownSites ${RefSNP}/${snp_dir}/${KnownSites} --bqsrBAQGapOpenPenalty $bqsrBAQGOP --deletions_default_quality $indelQUAL --insertions_default_quality $indelQUAL -o ${BAM_PREFIX}.recalibration_report2.grp -U ALLOW_N_CIGAR_READS --quantizing_levels 24 \n";
	push (@FilesToCopy, "${BAM_PREFIX}.recalibration_report2.grp");
	$Stage = "$StageNumber $LI $TI GATK BaseRecalibrator2";
	if ($DoneBQSRreports == 0) {
		system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx20g -jar $GATK -nct $Cpu_BQSR -T BaseRecalibrator -R ${RefGenome}/${ref}.fa -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -L ${RefSNP}/${snp_dir}/BQSR_${BqsrSize}MB_check.interval_list -knownSites ${RefSNP}/${snp_dir}/${KnownSites} --bqsrBAQGapOpenPenalty $bqsrBAQGOP --deletions_default_quality $indelQUAL --insertions_default_quality $indelQUAL -o ${BAM_PREFIX}.recalibration_report2.grp -U ALLOW_N_CIGAR_READS --quantizing_levels 24 ");
		$CODE = __LINE__; &CheckExit;
	}
	# BQSR report 2
	# Changed to GATK4 due to R issues 1/19/2021
#	print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:ParallelGCThreads=4 -Xmx10g -jar $GATK -T AnalyzeCovariates -R ${RefGenome}/${ref}.fa -BQSR ${BAM_PREFIX}.recalibration_report2.grp -plots ${BAM_PREFIX}.BQSR2.pdf -U ALLOW_N_CIGAR_READS\n";
	print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx10g -jar $GATK4 AnalyzeCovariates -bqsr ${BAM_PREFIX}.recalibration_report2.grp -plots ${BAM_PREFIX}.BQSR2.pdf\n";
	push (@FilesToCopy, "${BAM_PREFIX}.BQSR2.pdf");
	$Stage = "$StageNumber $LI $TI GATK BaseRecalibrator2 Report";
	if ($DoneBQSRreports == 0) {
#		system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:ParallelGCThreads=4 -Xmx10g -jar $GATK -T AnalyzeCovariates -R ${RefGenome}/${ref}.fa -BQSR ${BAM_PREFIX}.recalibration_report2.grp -plots ${BAM_PREFIX}.BQSR2.pdf -U ALLOW_N_CIGAR_READS ");
		system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx10g -jar $GATK4 AnalyzeCovariates -bqsr ${BAM_PREFIX}.recalibration_report2.grp -plots ${BAM_PREFIX}.BQSR2.pdf ");
		$CODE = __LINE__; &CheckExit;
	}
	# BQSR report 3
#	print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:ParallelGCThreads=6 -Xmx10g -jar $GATK -T AnalyzeCovariates -R ${RefGenome}/${ref}.fa -before ${BAM_PREFIX}.recalibration_report.grp -after ${BAM_PREFIX}.recalibration_report2.grp -plots ${BAM_PREFIX}.BQSR3.pdf -U ALLOW_N_CIGAR_READS\n";
	print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx10g -jar $GATK4 AnalyzeCovariates -before ${BAM_PREFIX}.recalibration_report.grp -after ${BAM_PREFIX}.recalibration_report2.grp -plots ${BAM_PREFIX}.BQSR3.pdf\n";
	push (@FilesToCopy, "${BAM_PREFIX}.BQSR3.pdf");
	$Stage = "$StageNumber $LI $TI GATK BaseRecalibrator2 Report";
	if ($DoneBQSRreports == 0) {
#		system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:ParallelGCThreads=6 -Xmx10g -jar $GATK -T AnalyzeCovariates -R ${RefGenome}/${ref}.fa -before ${BAM_PREFIX}.recalibration_report.grp -after ${BAM_PREFIX}.recalibration_report2.grp -plots ${BAM_PREFIX}.BQSR3.pdf -U ALLOW_N_CIGAR_READS ");
		system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx10g -jar $GATK4 AnalyzeCovariates -before ${BAM_PREFIX}.recalibration_report.grp -after ${BAM_PREFIX}.recalibration_report2.grp -plots ${BAM_PREFIX}.BQSR3.pdf ");
		$CODE = __LINE__; &CheckExit;
	}
	$TimeEnd = new Benchmark;
	$TimeDiff = timediff($TimeEnd, $TimeStart);
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber GATK BaseRecalibrator2\t${BAM_PREFIX}.bam\t", timestr($TimeDiff), "\n";
	&DirectorySize;
	system ("echo \"DONE DoneBQSRreports\" >DoneBQSRreports");

} # Closing bracket $DoBQSR block ~1912


#=pod
###############################################################################
# DEPTH OF COVERAGE
if ($DoBQSR == 1) { $BAM_SUFFIX = "realigned.recalibrated"; }
else { $BAM_SUFFIX = "realigned"; }

$StageNumber++;
$TimeStart = new Benchmark;
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber GATK DepthOfCoverage\tALL FILES\t\t\n";
print "GATK DepthOfCoverage\n";
print LOG "# GATK DepthOfCoverage\n";
if ($DoneCoverage == 1) { print LOG "# GATK DepthOfCoverage ALREADY DONE\n"; }

my $DOCSem = 1;
if (int($Cpu_Node / 4) > 1 ) {
	$DOCSem = int($Cpu_Node / 4);
	$Cpu_DOC = 5;								# 4 = 70% CPU so raised to 5 to try to get closer to 100%, 5 = 90%
}

my @DocThreads;
my $semDOC = Thread::Semaphore->new($DOCSem);	
foreach (@SeqForIndelTargetX) {
	$semDOC->down;
	$t = threads->new(\&DepthOfCoverage, $_);
	push(@DocThreads,$t);
	sleep 1;
}
foreach (@DocThreads) { $num = $_->join; }

#####
# 04/27/2021
# These will not be accurate for tissue-specific analyses like RNA-seq.
# The sid will be the international_id in the detail report.
# The ${BAM_PREFIX} will be the lab_id in the summary report.
# These will need to be restructured/rewritten for tissue specific analyses.
# For right now these are not important for RNA-seq so we'll just not upload them to the db.

my @Coverage;									# contains the mean coverage for each chromosome
my @SeqForDOCResults = @SeqForIndelTarget;		# contains all the chromosome abbreviations
push (@SeqForDOCResults,"UNMAPPED");
open DOC, ">${BAM_PREFIX}.DOC.summary.csv";
open DOCD, ">${BAM_PREFIX}.DOC.detail.csv";

print DOCD "sid\tchr\ttotal\tmean\tgranular_third_quartile\tgranular_median\tgranular_first_quartile\tp_5\tp_10\tp_15\tp_20\tp_25\tp_30\tp_40\tp_50\tp_80\tp_90\tp_100\tp_150\n";
foreach (@SeqForDOCResults) {
	my $chr = $_;
	open DOCTMP, "${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bam.coverage.sample_summary";
	while (<DOCTMP>) {
		my ($sid,$total,$mean,$granular_third_quartile,$granular_median,$granular_first_quartile,$p_5,$p_10,$p_15,$p_20,$p_25,$p_30,$p_40,$p_50,$p_80,$p_90,$p_100,$p_150) = split(/\s/,$_);
		# Added this to NOT include ChrM and unmapped in calculation of coverage because these skew the average coverage 12/5/2015
		if ($sid eq ${animal_id}) {
			if ($chr !~ m/m/i) { push (@Coverage,$mean); }
			print DOCD "$sid\t${chr}\t$total\t$mean\t$granular_third_quartile\t$granular_median\t$granular_first_quartile\t$p_5\t$p_10\t$p_15\t$p_20\t$p_25\t$p_30\t$p_40\t$p_50\t$p_80\t$p_90\t$p_100\t$p_150\n";
		}
	}
	close DOCTMP;
}

my $DOCAvg = Math::NumberCruncher::Mean(\@Coverage);
print "\n\n${BAM_PREFIX}\t${animal_id}\t$DOCAvg\n\n";
print DOC "${BAM_PREFIX},${animal_id},$DOCAvg\n";
close DOC;
close DOCD;
push (@FilesToCopy, "${BAM_PREFIX}.DOC.summary.csv");
push (@FilesToCopy, "${BAM_PREFIX}.DOC.detail.csv");

sub DepthOfCoverage {
	# Total run time is dictated by the largest chromosome (Chr1).  Minimizing the run time for this chr will optimize total run time.
	# We run DOC on individual chromosomes and write the output to a chromosome specific file.  We then read these outputs 
	# and generate summary and detail results.
	#UNMAPPED
	if ($_ eq "UNMAPPED") {	
		# 10/8/2015 Changed to read the single ${BAM_PREFIX}.realigned.bam rather than individual chr files to try to prevent the %wa spikes happening at this stage
		# 11/12/2019 Changed mem to 6G because a couple of high coverage genomes failed here due to not enough memory
		# 04/13/2021 Changed mem to 10G because lab_id 338975 (>100x) failed here due to not enough memory
		print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx10g -jar $GATK -nt $Cpu_DOC -R ${RefGenome}/${ref}.fa -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -T DepthOfCoverage -L UNMAPPED_contigs.interval_list -o ${BAM_PREFIX}.UNMAPPED.${BAM_SUFFIX}.bam.coverage -omitBaseOutput -omitIntervals --omitLocusTable -ct 5 -ct 10 -ct 15 -ct 20 -ct 25 -ct 30 -ct 40 -ct 50 -ct 80 -ct 90 -ct 100 -ct 150 --minBaseQuality 15 --minMappingQuality 30 --start 1 --stop 1000 --nBins 999 -dt NONE -U ALLOW_N_CIGAR_READS\n";
		$Stage = "$StageNumber $LI $TI GATK DepthOfCoverage UNMAPPED";
		if ($DoneCoverage == 0) {
			system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx10g -jar $GATK -nt $Cpu_DOC -R ${RefGenome}/${ref}.fa -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -T DepthOfCoverage -L UNMAPPED_contigs.interval_list -o ${BAM_PREFIX}.UNMAPPED.${BAM_SUFFIX}.bam.coverage -omitBaseOutput -omitIntervals --omitLocusTable -ct 5 -ct 10 -ct 15 -ct 20 -ct 25 -ct 30 -ct 40 -ct 50 -ct 80 -ct 90 -ct 100 -ct 150 --minBaseQuality 15 --minMappingQuality 30 --start 1 --stop 1000 --nBins 999 -dt NONE -U ALLOW_N_CIGAR_READS");
			$CODE = __LINE__; &CheckExit;
		}
	}
	else {
		print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx10g -jar $GATK -nt $Cpu_DOC -R ${RefGenome}/${ref}.fa -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -T DepthOfCoverage -L $_ -o ${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bam.coverage -omitBaseOutput -omitIntervals --omitLocusTable -ct 5 -ct 10 -ct 15 -ct 20 -ct 25 -ct 30 -ct 40 -ct 50 -ct 80 -ct 90 -ct 100 -ct 150 --minBaseQuality 15 --minMappingQuality 30 --start 1 --stop 1000 --nBins 999 -dt NONE -U ALLOW_N_CIGAR_READS\n";
		$Stage = "$StageNumber $LI $TI GATK DepthOfCoverage $_";
		if ($DoneCoverage == 0) {
			system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx10g -jar $GATK -nt $Cpu_DOC -R ${RefGenome}/${ref}.fa -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -T DepthOfCoverage -L $_ -o ${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bam.coverage -omitBaseOutput -omitIntervals --omitLocusTable -ct 5 -ct 10 -ct 15 -ct 20 -ct 25 -ct 30 -ct 40 -ct 50 -ct 80 -ct 90 -ct 100 -ct 150 --minBaseQuality 15 --minMappingQuality 30 --start 1 --stop 1000 --nBins 999 -dt NONE -U ALLOW_N_CIGAR_READS");
			$CODE = __LINE__; &CheckExit;
		}
	}	
	$semDOC->up;
}

$TimeEnd = new Benchmark;
$TimeDiff = timediff($TimeEnd, $TimeStart);
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber GATK DepthOfCoverage\t${BAM_PREFIX}.${BAM_SUFFIX}.bam\t", timestr($TimeDiff), "\n";
&DirectorySize;
system ("echo \"DONE Coverage\" >DoneCoverage");

###############################################################################
# ALIGNMENT and INSERT SUMMARY METRICS

$StageNumber++;
$TimeStart = new Benchmark;
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber ALIGNMENT SUMMARY METRICS\tALL FILES\t\t\n";
print LOG "# ALIGNMENT SUMMARY METRICS\n";
if ($DoneMetrics == 1) { print LOG "# ALIGNMENT SUMMARY METRICS ALREADY DONE\n"; }

# Added  ASSUME_SORTED=TRUE 07/08/2018
print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx10g -jar $Picard CollectMultipleMetrics -INPUT ${BAM_PREFIX}.${BAM_SUFFIX}.bam -OUTPUT ${BAM_PREFIX} -METRIC_ACCUMULATION_LEVEL LIBRARY -REFERENCE_SEQUENCE ${RefGenome}/${ref}.fa -PROGRAM CollectAlignmentSummaryMetrics -PROGRAM CollectInsertSizeMetrics -STOP_AFTER $CollectMetricsNumReads -TMP_DIR ${cwd}/tmp -ASSUME_SORTED TRUE\n";
$Stage = "$StageNumber $LI $TI ALIGNMENT and INSERT SUMMARY METRICS $_";
if ($DoneMetrics == 0) {
	system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx10g -jar $Picard CollectMultipleMetrics -INPUT ${BAM_PREFIX}.${BAM_SUFFIX}.bam -OUTPUT ${BAM_PREFIX} -METRIC_ACCUMULATION_LEVEL LIBRARY -REFERENCE_SEQUENCE ${RefGenome}/${ref}.fa -PROGRAM CollectAlignmentSummaryMetrics -PROGRAM CollectInsertSizeMetrics -STOP_AFTER $CollectMetricsNumReads -TMP_DIR ${cwd}/tmp -ASSUME_SORTED TRUE");
	$CODE = __LINE__; &CheckExit;
}

# Added to collect metrics on Unmapped.bam 05/30/2019
print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx10g -jar $Picard CollectAlignmentSummaryMetrics -INPUT ${BAM_PREFIX}.Unmapped.bam -OUTPUT ${BAM_PREFIX}.Unmapped.alignment_summary_metrics -METRIC_ACCUMULATION_LEVEL LIBRARY -REFERENCE_SEQUENCE ${RefGenome}/${ref}.fa -STOP_AFTER $CollectMetricsNumReads -TMP_DIR ${cwd}/tmp -ASSUME_SORTED TRUE\n";
$Stage = "$StageNumber $LI $TI ALIGNMENT and INSERT SUMMARY METRICS $_";
if ($DoneMetrics == 0) {
	system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx10g -jar $Picard CollectAlignmentSummaryMetrics -INPUT ${BAM_PREFIX}.Unmapped.bam -OUTPUT ${BAM_PREFIX}.Unmapped.alignment_summary_metrics -METRIC_ACCUMULATION_LEVEL LIBRARY -REFERENCE_SEQUENCE ${RefGenome}/${ref}.fa -STOP_AFTER $CollectMetricsNumReads -TMP_DIR ${cwd}/tmp -ASSUME_SORTED TRUE");
	$CODE = __LINE__; &CheckExit;
	&AlignmentSummary;
}

# Check to make sure that the ${BAM_PREFIX}.insert_size_metrics file can be opened
# For a sample that only had SE data such as RNA-seq there is no PE data to estimate insert size
# and thus there is no ${BAM_PREFIX}.insert_size_metrics output file. When we tried to open this
# in &AlignmentSummary it would fail silently and the whole analysis would stop so we now check
# to see if the file is present before we call the subroutine. This means that if we do have PE data
# and the insert size failed for some reason then we still won't have these summary files. Added 03/24/2019
if (!(-e -f "${BAM_PREFIX}.insert_size_metrics")) {
	print LOG "# File not found: ${BAM_PREFIX}.insert_size_metrics\n";
	print "# File not found: ${BAM_PREFIX}.insert_size_metrics\n";
}
else {
	if ($DoneMetrics == 0) {
		&InsertSummary;
	}
	push (@FilesToCopy, "${BAM_PREFIX}.insert_size_metrics");
	push (@FilesToCopy, "${BAM_PREFIX}.insert_size_metrics.csv");
	push (@FilesToCopy, "${BAM_PREFIX}.insert_size_histogram.pdf");
}

push (@FilesToCopy, "${BAM_PREFIX}.alignment_summary_metrics");
push (@FilesToCopy, "${BAM_PREFIX}.Unmapped.alignment_summary_metrics");			# Added 12/05/2019
push (@FilesToCopy, "${BAM_PREFIX}.alignment_summary_metrics.csv");
push (@FilesToCopy, "${BAM_PREFIX}.base_distribution_by_cycle.pdf");				# New 07/07/2018
push (@FilesToCopy, "${BAM_PREFIX}.quality_by_cycle.pdf");							# New 07/07/2018
push (@FilesToCopy, "${BAM_PREFIX}.quality_distribution.pdf");						# New 07/07/2018

$TimeEnd = new Benchmark;
$TimeDiff = timediff($TimeEnd, $TimeStart);
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber ALIGNMENT SUMMARY METRICS\t${BAM_PREFIX}.bam\t", timestr($TimeDiff), "\n";
&DirectorySize;
system ("echo \"DONE Metrics\" >DoneMetrics");


###############################################################################
# HAPLOTYPE CALLER & CALLABLE LOCI
if ($DoBQSR == 1) { $BAM_SUFFIX = "realigned.recalibrated"; }
else { $BAM_SUFFIX = "realigned"; }

$StageNumber++;
$TimeStart = new Benchmark;
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber GATK HaplotypeCaller\tALL FILES\t\t\n";
print "BEGIN GATK HaplotypeCaller\n";
print LOG "# GATK HaplotypeCaller\n";

if ($DoHC == 0) {
	# 04/26/2021 Added this back in order to skip HC for transcriptomes. 
	# The logic for skipping HaplotypeCaller was already worked out for when the DoneHC file is present.
	# Therefore, if we want to skip HC from the input flag we just set the $DoneHC to 1 here and print a different description to the log.
	print LOG "# GATK HaplotypeCaller input flag --hc set to 0 so we're skipping HaplotypeCaller by setting DoneHC=1\n";
	$DoneHC = 1;
}
if ($DoneHC == 1) { print LOG "# GATK HaplotypeCaller ALREADY DONE\n"; }

my $HCSem = 1;
if (int($Cpu_Node / 4) > 1 ) {
	$HCSem = int($Cpu_Node / 4);
	$Cpu_HC = 4;								# 4 is optimal on MUG hardware
}

my $semHC = Thread::Semaphore->new($HCSem);
my @HaplotypeCallerThreads;
foreach (@SeqForIndelTargetX) {
	$semHC->down;
	$t = threads->new(\&HaplotypeCaller, $_);
	push (@HaplotypeCallerThreads,$t);
	
	# Push all of the gvcf into the copy array
	if ($DoHC == 1) {
		push (@FilesToCopy, "${BAM_PREFIX}.${_}.g.vcf.gz");
		push (@FilesToCopy, "${BAM_PREFIX}.${_}.g.vcf.gz.md5");
		push (@FilesToCopy, "${BAM_PREFIX}.${_}.g.vcf.gz.tbi");
		push (@FilesToCopy, "${BAM_PREFIX}.${_}.g.vcf.gz.tbi.md5");
		push (@FilesToCopy, "${BAM_PREFIX}.CallableLoci.${_}.bed.gz");
		push (@FilesToCopy, "${BAM_PREFIX}.CallableLoci.${_}.bed.gz.md5");
		push (@FilesToCopy, "${BAM_PREFIX}.CallableLoci.${_}.summary.txt");
	}
	sleep 1;
}
foreach (@HaplotypeCallerThreads) { my $num = $_->join; }

# CombineGVCFs for UNMAPPED
if ($DoHC == 1) { print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx15g -jar $GATK -T CombineGVCFs -R ${RefGenome}/${ref}.fa -V UNMAPPED_contigsMerge.list -o ${BAM_PREFIX}.UNMAPPED.g.vcf.gz\n"; }
$Stage = "$StageNumber $LI $TI GATK HaplotypeCaller CombineGVCFs ${BAM_PREFIX}.UNMAPPED.g.vcf.gz";
if ($DoneHC == 0 and $DoHC == 1) {
	system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx15g -jar $GATK -T CombineGVCFs -R ${RefGenome}/${ref}.fa -V UNMAPPED_contigsMerge.list -o ${BAM_PREFIX}.UNMAPPED.g.vcf.gz");
	$CODE = __LINE__; &CheckExit;
}
if ($DoHC == 1) { print LOG "md5sum ${BAM_PREFIX}.UNMAPPED.g.vcf.gz >${BAM_PREFIX}.UNMAPPED.g.vcf.gz.md5\n"; }
$Stage = "$StageNumber $LI $TI GATK HaplotypeCaller md5sum ${BAM_PREFIX}.UNMAPPED.g.vcf.gz";
if ($DoneHC == 0 and $DoHC == 1) {
	system ("md5sum ${BAM_PREFIX}.UNMAPPED.g.vcf.gz >${BAM_PREFIX}.UNMAPPED.g.vcf.gz.md5");
	$CODE = __LINE__; &CheckExit;
}
if ($DoHC == 1) { print LOG "md5sum ${BAM_PREFIX}.UNMAPPED.g.vcf.gz.tbi >${BAM_PREFIX}.UNMAPPED.g.vcf.gz.tbi.md5\n"; }
$Stage = "$StageNumber $LI $TI GATK HaplotypeCaller md5sum";
if ($DoneHC == 0 and $DoHC == 1) {
	system ("md5sum ${BAM_PREFIX}.UNMAPPED.g.vcf.gz.tbi >${BAM_PREFIX}.UNMAPPED.g.vcf.gz.tbi.md5");
	$CODE = __LINE__; &CheckExit;
	# Move the 2 lines below inside block for when we skip doing HaplotypeCaller 04/26/2021
	&CallableLoci;	# Parse the CallableLoci summary files to create a single file
	push (@FilesToCopy, "${BAM_PREFIX}.CallableLoci.summary.txt");
}

sub HaplotypeCaller {
	# UNMAPPED
	# We use one semaphor to run all the chunks of UNMAPPED. After HC is done we need to CombineGVCFs for the Unmapped chunks into a single UNMAPPED.g.vcf
	# For unmapped contigs multithreading on a large number of contigs kills performance. Therefore, we split the large number of unmapped contigs into smaller chunks
	# and multithreading with -nct works fine for chunks of 50 (tested). -nct was added back in v0.5.5 (06/05/2018)
	# NOTE: CallableLoci cannot be threaded with -nt or -nct !!!!!!
	if ($_ eq "UNMAPPED") {
		my $uc = 1;			
		while ($uc <= $NumUnmappedHClists) {
			# Added pcr_indel_model NONE for dogs 12/04/2015
			$Stage = "$StageNumber $LI $TI GATK HaplotypeCaller $_";
			if ($Analysis eq 'wgs' or $Analysis eq 'faire' or $Analysis eq 'atac') {
				if ($DoHC == 1) { print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx15g -jar $GATK -nct $Cpu_HC -ERC GVCF -T HaplotypeCaller -R ${RefGenome}/${ref}.fa -L UNMAPPED_contigs${uc}.interval_list -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -o ${BAM_PREFIX}.UNMAPPED${uc}.g.vcf.gz --heterozygosity $Heterozygosity --pcr_indel_model NONE --useNewAFCalculator \n"; }
				if ($DoneHC == 0 and $DoHC == 1) {
					system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx15g -jar $GATK -nct $Cpu_HC -ERC GVCF -T HaplotypeCaller -R ${RefGenome}/${ref}.fa -L UNMAPPED_contigs${uc}.interval_list -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -o ${BAM_PREFIX}.UNMAPPED${uc}.g.vcf.gz --heterozygosity $Heterozygosity --pcr_indel_model NONE --useNewAFCalculator ");
					$CODE = __LINE__; &CheckExit;
				}
			}
			elsif ($Analysis eq 'rna') {
				if ($DoHC == 1) { print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx15g -jar $GATK -nct $Cpu_HC -ERC GVCF -T HaplotypeCaller -R ${RefGenome}/${ref}.fa -L UNMAPPED_contigs${uc}.interval_list -I ${LI}.tissue.bam.list -o ${BAM_PREFIX}.UNMAPPED${uc}.g.vcf.gz --sample_name ${animal_id} --heterozygosity $Heterozygosity --pcr_indel_model NONE -dontUseSoftClippedBases -U ALLOW_N_CIGAR_READS --useNewAFCalculator \n"; }
				if ($DoneHC == 0 and $DoHC == 1) {
					system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx15g -jar $GATK -nct $Cpu_HC -ERC GVCF -T HaplotypeCaller -R ${RefGenome}/${ref}.fa -L UNMAPPED_contigs${uc}.interval_list -I ${LI}.tissue.bam.list -o ${BAM_PREFIX}.UNMAPPED${uc}.g.vcf.gz --sample_name ${animal_id} --heterozygosity $Heterozygosity --pcr_indel_model NONE -dontUseSoftClippedBases -U ALLOW_N_CIGAR_READS --useNewAFCalculator ");
					$CODE = __LINE__; &CheckExit;
				}
			}
			$uc++;
		}
		# Run CallableLoci once for all the UNMAPPED_contigs.interval_list
		if ($Analysis eq 'wgs' or $Analysis eq 'faire' or $Analysis eq 'atac') {
			if ($DoHC == 1) { print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx15g -jar $GATK -T CallableLoci -R ${RefGenome}/${ref}.fa -L UNMAPPED_contigs.interval_list -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -summary ${BAM_PREFIX}.CallableLoci.${_}.summary.txt -o ${BAM_PREFIX}.CallableLoci.${_}.bed\n"; }
			if ($DoneHC == 0 and $DoHC == 1) {
				system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx15g -jar $GATK -T CallableLoci -R ${RefGenome}/${ref}.fa -L UNMAPPED_contigs.interval_list -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -summary ${BAM_PREFIX}.CallableLoci.${_}.summary.txt -o ${BAM_PREFIX}.CallableLoci.${_}.bed");
				system ("pigz -f -9 -p${Cpu_HC} ${BAM_PREFIX}.CallableLoci.${_}.bed");
				system ("md5sum ${BAM_PREFIX}.CallableLoci.${_}.bed.gz >${BAM_PREFIX}.CallableLoci.${_}.bed.gz.md5");
			}
		}
		elsif ($Analysis eq 'rna') { # Added 03/23/2019
			if ($DoHC == 1) { print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx15g -jar $GATK -T CallableLoci -R ${RefGenome}/${ref}.fa -L UNMAPPED_contigs.interval_list -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -summary ${BAM_PREFIX}.CallableLoci.${_}.summary.txt -o ${BAM_PREFIX}.CallableLoci.${_}.bed -U ALLOW_N_CIGAR_READS\n"; }
			if ($DoneHC == 0 and $DoHC == 1) {
				system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx15g -jar $GATK -T CallableLoci -R ${RefGenome}/${ref}.fa -L UNMAPPED_contigs.interval_list -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -summary ${BAM_PREFIX}.CallableLoci.${_}.summary.txt -o ${BAM_PREFIX}.CallableLoci.${_}.bed -U ALLOW_N_CIGAR_READS");
				system ("pigz -f -9 -p${Cpu_HC} ${BAM_PREFIX}.CallableLoci.${_}.bed");
				system ("md5sum ${BAM_PREFIX}.CallableLoci.${_}.bed.gz >${BAM_PREFIX}.CallableLoci.${_}.bed.gz.md5");
			}
		}
	}	
	elsif ($_ ne "UNMAPPED") {
		# Added pcr_indel_model NONE for dogs 12/04/2015
		if ($Analysis eq 'wgs' or $Analysis eq 'faire' or $Analysis eq 'atac') {
			if ($DoHC == 1) { print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx15g -jar $GATK -nct $Cpu_HC -ERC GVCF -T HaplotypeCaller -R ${RefGenome}/${ref}.fa -L $_ -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -o ${BAM_PREFIX}.${_}.g.vcf.gz --heterozygosity $Heterozygosity --pcr_indel_model NONE --useNewAFCalculator \n"; }
			$Stage = "$StageNumber $LI $TI GATK HaplotypeCaller $_";
			if ($DoneHC == 0 and $DoHC == 1) {
				system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx15g -jar $GATK -nct $Cpu_HC -ERC GVCF -T HaplotypeCaller -R ${RefGenome}/${ref}.fa -L $_ -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -o ${BAM_PREFIX}.${_}.g.vcf.gz --heterozygosity $Heterozygosity --pcr_indel_model NONE --useNewAFCalculator ");
				$CODE = __LINE__; &CheckExit;
			}
			# CallableLoci
			if ($DoHC == 1) { print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx15g -jar $GATK -T CallableLoci -R ${RefGenome}/${ref}.fa -L $_ -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -summary ${BAM_PREFIX}.CallableLoci.${_}.summary.txt -o ${BAM_PREFIX}.CallableLoci.${_}.bed\n"; }
			if ($DoneHC == 0 and $DoHC == 1) {
				system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx15g -jar $GATK -T CallableLoci -R ${RefGenome}/${ref}.fa -L $_ -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -summary ${BAM_PREFIX}.CallableLoci.${_}.summary.txt -o ${BAM_PREFIX}.CallableLoci.${_}.bed");
				$CODE = __LINE__; &CheckExit;
				system ("pigz -f -9 -p${Cpu_HC} ${BAM_PREFIX}.CallableLoci.${_}.bed");
				system ("md5sum ${BAM_PREFIX}.CallableLoci.${_}.bed.gz >${BAM_PREFIX}.CallableLoci.${_}.bed.gz.md5");
			}
		}
		elsif ($Analysis eq 'rna') {
			if ($DoHC == 1) { print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx15g -jar $GATK -nct $Cpu_HC -ERC GVCF -T HaplotypeCaller -R ${RefGenome}/${ref}.fa -L $_ -I ${LI}.tissue.bam.list -o ${BAM_PREFIX}.${_}.g.vcf.gz --sample_name ${animal_id} --heterozygosity $Heterozygosity --pcr_indel_model NONE -dontUseSoftClippedBases -U ALLOW_N_CIGAR_READS --useNewAFCalculator \n"; }
			$Stage = "$StageNumber $LI $TI GATK HaplotypeCaller $_";
			if ($DoneHC == 0 and $DoHC == 1) {
				system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx15g -jar $GATK -nct $Cpu_HC -ERC GVCF -T HaplotypeCaller -R ${RefGenome}/${ref}.fa -L $_ -I ${LI}.tissue.bam.list -o ${BAM_PREFIX}.${_}.g.vcf.gz --sample_name ${animal_id} --heterozygosity $Heterozygosity --pcr_indel_model NONE -dontUseSoftClippedBases -U ALLOW_N_CIGAR_READS --useNewAFCalculator ");
				$CODE = __LINE__; &CheckExit;
			}
			# CallableLoci Added 03/23/2019
			if ($DoHC == 1) { print LOG "java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx15g -jar $GATK -T CallableLoci -R ${RefGenome}/${ref}.fa -L $_ -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -summary ${BAM_PREFIX}.CallableLoci.${_}.summary.txt -o ${BAM_PREFIX}.CallableLoci.${_}.bed -U ALLOW_N_CIGAR_READS\n"; }
			if ($DoneHC == 0 and $DoHC == 1) {
				system ("java -Djava.io.tmpdir=${cwd}/tmp -XX:+UseParallelGC -XX:ParallelGCThreads=2 -Xmx15g -jar $GATK -T CallableLoci -R ${RefGenome}/${ref}.fa -L $_ -I ${BAM_PREFIX}.${BAM_SUFFIX}.bam -summary ${BAM_PREFIX}.CallableLoci.${_}.summary.txt -o ${BAM_PREFIX}.CallableLoci.${_}.bed -U ALLOW_N_CIGAR_READS");
				$CODE = __LINE__; &CheckExit;
				system ("pigz -f -9 -p${Cpu_HC} ${BAM_PREFIX}.CallableLoci.${_}.bed");
				system ("md5sum ${BAM_PREFIX}.CallableLoci.${_}.bed.gz >${BAM_PREFIX}.CallableLoci.${_}.bed.gz.md5");
			}
		}
		$Stage = "$StageNumber $LI $TI GATK HaplotypeCaller md5sum ${BAM_PREFIX}.${_}.g.vcf.gz";
		$Stage = "$StageNumber $LI $TI GATK HaplotypeCaller md5sum ${BAM_PREFIX}.${_}.g.vcf.gz.tbi";
		if ($DoneHC == 0 and $DoHC == 1) {
			system ("md5sum ${BAM_PREFIX}.${_}.g.vcf.gz >${BAM_PREFIX}.${_}.g.vcf.gz.md5");
			$CODE = __LINE__; &CheckExit;
			system ("md5sum ${BAM_PREFIX}.${_}.g.vcf.gz.tbi >${BAM_PREFIX}.${_}.g.vcf.gz.tbi.md5");
			$CODE = __LINE__; &CheckExit;
		}
	}	
	$semHC->up;
}

$TimeEnd = new Benchmark;	#grab end time
$TimeDiff = timediff($TimeEnd, $TimeStart);
$TimeStamp = timestamp();
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber GATK HaplotypeCaller\t${BAM_PREFIX}.${BAM_SUFFIX}.bam\t", timestr($TimeDiff), "\n";
&DirectorySize;
system ("echo \"DONE HC\" >DoneHC");

#=cut
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
} # UNMAPPED ONLY ~line 1580
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
#=pod
if ($Analysis eq "atac") {
	###############################################################################
	# ATAC PROCESSING
	#
	# 08/07/2019 We process all of the ATAC seq for a tissue_id together which generates genotype calls from HaplotypeCaller use all of the data.
	# For ATAC seq we want to use all of the data from a sample for calling genotypes but we want to collect stats
	#  on a per tissue and per library basis. However, since there may be multiple libraries per tissue_id and these library ID's
	#  will be duplicated across tissues from the same lab_id we have a problem if we use all of the tissue_id from a lab_id.
	#  This will cause markduplicates to treat the same library ID from different tisses as the same when in fact it is not.
	#  Therefore, at this time I think we're restricted to calling genotypes on a per lab_id and tissue_id basis.
	# 
	# However, we need to have statistics on a per library basis. The samtools commands to get stats by library are very slow so we
	#  extract all of the libraries into individual [LI]_[TI].[library].${BAM_SUFFIX}.bam files and then run the stats on each.

	# $NumLibraries has the number of unique libraries for the LI
	# @Unique_Libraries has the array of unique libraries

	# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

	$StageNumber++;
	$TimeStart = new Benchmark;
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber ATAC STATS\tALL FILES\t\t\n";
	print "ATAC STATS\n";
	print LOG "# ATAC STATS\n";
	if ($DoneAtacStats == 1) { print LOG "# ATAC STATS ALREADY DONE\n"; }
	$Stage = "$StageNumber $LI $TI ATAC ";

	# Load the Python environment for MACS2
	# This will need changed if there is any modifications to MACS2
#	print LOG "source /storage/hpc/group/UMAG/VIRTUALENV/MACS2.1.2/MACS2/bin/activate\n";
#	system ("source /storage/hpc/group/UMAG/VIRTUALENV/MACS2.1.2/MACS2/bin/activate");
	#$CODE = __LINE__; &CheckExit;

	# append results of various counts to the summary file
	if ($DoneAtacStats == 0) {
		open ATACSUM, ">>${BAM_PREFIX}.ATAC.SUMMARY.csv";
		print ATACSUM "lab_id\ttissue_id\tlibrary\tall\tdups\tproper_pair\tproper_pair_unique\tproper_pair_unique_nodups\tmt\tpercent_mt\tnrf\n";
	}
	push (@FilesToCopy, "${BAM_PREFIX}.ATAC.SUMMARY.csv");
	
	my $ATACSem = 1;
	if (int($Cpu_Node / 2) > 1 ) {
		$ATACSem = int($Cpu_Node / 2);
		$Cpu_ATAC = 2;								# number of threads for samtools compression
	}
	my @ATACThreads;
	my $semATAC = Thread::Semaphore->new($ATACSem);	
	foreach (@Unique_Libraries) {
		$semATAC->down;
		$t = threads->new(\&ATACstats, $_);
		push(@ATACThreads,$t);
		# Push all of the library bams into the copy array
		push (@FilesToCopy, "${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bam");
		push (@FilesToCopy, "${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bam.md5");
		push (@FilesToCopy, "${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bam.bai");
		push (@FilesToCopy, "${BAM_PREFIX}.${_}.${BAM_SUFFIX}.bam.bai.md5");
		# NAME_peaks.xls, NAME_peaks.narrowPeak, NAME_summits.bed, NAME_model.r
		push (@FilesToCopy, "${BAM_PREFIX}.${_}.${BAM_SUFFIX}_peaks.xls");
		push (@FilesToCopy, "${BAM_PREFIX}.${_}.${BAM_SUFFIX}_peaks.narrowPeak");
		push (@FilesToCopy, "${BAM_PREFIX}.${_}.${BAM_SUFFIX}_summits.bed");
		#push (@FilesToCopy, "${BAM_PREFIX}.${_}.${BAM_SUFFIX}_model.r");
		#push (@FilesToCopy, "${BAM_PREFIX}.${_}.${BAM_SUFFIX}_model.pdf");

		if ($NumLibraries > 1) { push (@FilesToCopy, "${BAM_PREFIX}.jaccard.txt"); }
		sleep 1;
	}
	foreach (@ATACThreads) { $num = $_->join; }

	sub ATACstats {
			$Stage = "$StageNumber $LI $TI ATAC Library $_ ";
		if ($NumLibraries == 1) {
			# Since we only have one library we copy the [Lab_ID].${BAM_SUFFIX}.bam to [Lab_ID].[library].${BAM_SUFFIX}.bam
			# This is wasteful but right now is an easier solution so that we have a bam for each library
			$Library = $_;
			print LOG "cp ${BAM_PREFIX}.${BAM_SUFFIX}.bam ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam\n";
			if ($DoneAtacStats == 0) {
				system ("cp ${BAM_PREFIX}.${BAM_SUFFIX}.bam ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam");
				$CODE = __LINE__; &CheckExit;
			}
		}
		else {
			$Library = $_;
			print LOG "$Samtools view -b -h -\@ $Cpu_ATAC -l ${Library} -F 0x900 ${BAM_PREFIX}.${BAM_SUFFIX}.bam -o ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam\n";
			if ($DoneAtacStats == 0) {
				system ("$Samtools view -b -h -\@ $Cpu_ATAC -l ${Library} -F 0x900 ${BAM_PREFIX}.${BAM_SUFFIX}.bam -o ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam");
				$CODE = __LINE__; &CheckExit;
			}
		}
		print LOG "$Samtools index ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam\n";
		print LOG "md5sum ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam >${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam.md5\n";
		print LOG "md5sum ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam.bai >${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam.bai.md5\n";
		# All reads
		print LOG "$Samtools view -c -F0x900 ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam\n"; 
		# Duplicate reads (PCR & Optical)
		print LOG "$Samtools view -c -F0x900 -f1024 ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam\n"; 
		# Proper pair
		print LOG "$Samtools view -c -F0x900 -f2 ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam\n"; 
		# Proper pair Unique
		print LOG "$Samtools view -c -F0x900 -f2 -q3 ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam\n"; 
		# Proper pair Unique NoDups
		print LOG "$Samtools view -c -F0x900 -f2 -q3 -F1024 ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam\n"; 
		# MT
		print LOG "$Samtools view -c -F0x900 ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam MT\n"; 

		if ($DoneAtacStats == 0) {
			system ("$Samtools index ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam");
			$CODE = __LINE__; &CheckExit;
			system ("md5sum ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam >${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam.md5");
			$CODE = __LINE__; &CheckExit;
			system ("md5sum ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam.bai >${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam.bai.md5");
			$CODE = __LINE__; &CheckExit;

			# All reads
			my $A_All = `$Samtools view -c -F0x900 ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam`; 
			chomp $A_All;		
			# Duplicate reads (PCR & Optical)
			my $A_Dup = `$Samtools view -c -F0x900 -f1024 ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam`; 
			chomp $A_Dup;	
			# Proper pair
			my $A_PP = `$Samtools view -c -F0x900 -f2 ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam`; 
			chomp $A_PP;	
			# Proper pair Unique
			my $A_PPU = `$Samtools view -c -F0x900 -f2 -q3 ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam`; 
			chomp $A_PPU;		
			# Proper pair Unique NoDups
			my $A_PPUD = `$Samtools view -c -F0x900 -f2 -q3 -F1024 ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam`; 
			chomp $A_PPUD;
			# MT
			my $A_MT = `$Samtools view -c -F0x900 ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam MT`; 
			chomp $A_MT;
			my $PercentMT = $A_MT / $A_All;
			my $NRF = ($A_PPUD - $A_MT) / ($A_All - $A_MT);
			print ATACSUM "$LI\t$TI\t$Library\t$A_All\t$A_Dup\t$A_PP\t$A_PPU\t$A_PPUD\t$A_MT\t$PercentMT\t$NRF\n";
		}
		# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
		# We can do peak calling here
		# We need to activate the python environment within the subroutine
		print LOG "source /storage/hpc/group/UMAG/VIRTUALENV/MACS2.1.2/MACS2/bin/activate\n";
		if ($DoneAtacStats == 0) {
			system ("source /storage/hpc/group/UMAG/VIRTUALENV/MACS2.1.2/MACS2/bin/activate");
		}
		# NAME_peaks.xls, NAME_negative_peaks.xls, NAME_peaks.bed , NAME_summits.bed, NAME_model.r
		print LOG "macs2 callpeak -t ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam -f BAMPE -g hs -n ${BAM_PREFIX}.${Library}.${BAM_SUFFIX} -q 0.05\n";
		if ($DoneAtacStats == 0) {
			system ("macs2 callpeak -t ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}.bam -f BAMPE -g hs -n ${BAM_PREFIX}.${Library}.${BAM_SUFFIX} -q 0.05");
			$CODE = __LINE__; &CheckExit;
		}		
		# Sort the bed output so that the jaccard metric is correct
		# sort -k1,1 -k2,2n test_peaks.narrowPeak > test_peaks.narrowPeak.sorted.bed
		print LOG "mv ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}_peaks.narrowPeak.sorted ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}_peaks.narrowPeak.bed\n";
		print LOG "sort -k1,1 -k2,2n ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}_peaks.narrowPeak > ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}_peaks.narrowPeak.sorted\n";
		print LOG "deactivate\n";

		if ($DoneAtacStats == 0) {
			system ("sort -k1,1 -k2,2n ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}_peaks.narrowPeak > ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}_peaks.narrowPeak.sorted");
			$CODE = __LINE__; &CheckExit;
			system ("mv ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}_peaks.narrowPeak.sorted ${BAM_PREFIX}.${Library}.${BAM_SUFFIX}_peaks.narrowPeak.bed");
			$CODE = __LINE__; &CheckExit;
			# Rscript NAME_model.r
			system ("deactivate");
		}

		# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

		$semATAC->up;
	}

	if ($DoneAtacStats == 0) { close ATACSUM; }

	# Run the jaccard metrics if there is more than one library
	if ($NumLibraries > 1 and $DoneAtacStats == 0) {
		open JAC, ">${BAM_PREFIX}.jaccard.txt";
		print JAC "lab_id,tissue_id,library1,library2,intersection,union_intersection,jaccard,n_intersections\n";
		my $i = 0;
		my $j = 1;
		print "NumLibraries: $NumLibraries\ti:$i\tj:$j\n";
		while ($i < $NumLibraries and $j <= ($NumLibraries + 1)) {
			while ($j <= $NumLibraries) {
				# time bedtools jaccard -a test_peaks.narrowPeak -b test2_peaks.narrowPeak
				# intersection union-intersection jaccard  n_intersections
				# 121510       1109967            0.109472 634
				# @Unique_Libraries
				my $Lib1 = @Unique_Libraries[$i];
				my $Lib2 = @Unique_Libraries[$j];
				system ("bedtools jaccard -a ${BAM_PREFIX}.${Lib1}.${BAM_SUFFIX}_peaks.narrowPeak.bed -b ${BAM_PREFIX}.${Lib2}.${BAM_SUFFIX}_peaks.narrowPeak.bed | tail -n1 >${Lib1}_${Lib2}.jaccard");
				$CODE = __LINE__; &CheckExit;
				my ($int, $unioni, $jaccard, $n_inter) = split (/\s+/,`cat ${Lib1}_${Lib2}.jaccard`);
				print JAC "$LI,$TI,$Lib1,$Lib2,$int,$unioni,$jaccard,$n_inter\n";
				$j++;
			}			
			$i++;
		}
		close JAC;
	}

	$TimeEnd = new Benchmark;
	$TimeDiff = timediff($TimeEnd, $TimeStart);
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber ATAC STATS\tALL FILES\t", timestr($TimeDiff), "\n";
	&DirectorySize;
	system ("echo \"DONE AtacStats\" >DoneAtacStats");
} # End of ATAC if

#=cut

################################################################################
# WASP & FeatureCounts
if ($Analysis eq "rna") {
	$StageNumber++;
	$TimeStart = new Benchmark;
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber WASP & FeatureCounts\tALL FILES\t\t\n";
	print "WASP & FeatureCounts\n";
	print LOG "# WASP & FeatureCounts\n";

	if ($DoWasp == 1) {
		# WASP filtering
		# Create bam file with the wasp tag reads that pass (-d vW:1) and a file with all the other reads (--output-unselected)
		print LOG "# WASP FILTERING samtools view 1\n";
		print LOG "samtools view -\@ 6 -d vW:1 -b -o ${BAM_PREFIX}.wasp.bam --output-unselected ${BAM_PREFIX}.NOTwasp.bam ${BAM_PREFIX}.${BAM_SUFFIX}.bam\n";
		if ($DoneWasp == 0) {
			system ("samtools view -\@ 6 -d vW:1 -b -o ${BAM_PREFIX}.wasp.bam --output-unselected ${BAM_PREFIX}.NOTwasp.bam ${BAM_PREFIX}.${BAM_SUFFIX}.bam");
			$CODE = __LINE__; &CheckExit;
		}
		print LOG "samtools index -\@ 8 -b ${BAM_PREFIX}.wasp.bam\n";
		if ($DoneWasp == 0) {
			system ("samtools index -\@ 8 -b ${BAM_PREFIX}.wasp.bam");
			$CODE = __LINE__; &CheckExit;
		}
		print LOG "samtools index -\@ 8 -b ${BAM_PREFIX}.NOTwasp.bam\n";
		if ($DoneWasp == 0) {
			system ("samtools index -\@ 8 -b ${BAM_PREFIX}.NOTwasp.bam");
			$CODE = __LINE__; &CheckExit;
		}
		# Now we need all of the reads from the ${BAM_PREFIX}.NOTwasp1.bam that do not have a wasp flag (-d vW)
		print LOG "# WASP FILTERING samtools view 2\n";
		print LOG "samtools view -\@ 6 -d vW -b -o ${BAM_PREFIX}.waspOther.bam --output-unselected ${BAM_PREFIX}.NoWaspTags.bam ${BAM_PREFIX}.NOTwasp.bam\n";
		if ($DoneWasp == 0) {
			system ("samtools view -\@ 6 -d vW -b -o ${BAM_PREFIX}.waspOther.bam --output-unselected ${BAM_PREFIX}.NoWaspTags.bam ${BAM_PREFIX}.NOTwasp.bam");
			$CODE = __LINE__; &CheckExit;
		}
		# ${BAM_PREFIX}.NoWaspTags.bam contains reads that do not have any WASP tag. These are reads that did not overlap a variant.
		# ${BAM_PREFIX}.wasp.bam contain reads that overlapped a variant but did not change the mapping (Passed WASP filtering)

		# Merge the bams that we want to use for feature counts
		print LOG "# WASP FILTERING samtools merge\n";
		print LOG "samtools merge -\@ 6 -c -p -f -o ${BAM_PREFIX}.Final.bam ${BAM_PREFIX}.NoWaspTags.bam ${BAM_PREFIX}.wasp.bam\n";
		if ($DoneWasp == 0) {
			system ("samtools merge -\@ 6 -c -p -f -o ${BAM_PREFIX}.Final.bam ${BAM_PREFIX}.NoWaspTags.bam ${BAM_PREFIX}.wasp.bam");
			$CODE = __LINE__; &CheckExit;
		}
		print LOG "samtools index -\@ 8 -b ${BAM_PREFIX}.Final.bam\n";
		if ($DoneWasp == 0) {
			system ("samtools index -\@ 8 -b ${BAM_PREFIX}.Final.bam");
			$CODE = __LINE__; &CheckExit;
		}
		# Generate FeatureCounts Input
		# Write Paired Read file
		print LOG "# Generate FeatureCounts Input Write Paired Read file\n";
		print LOG "samtools view -\@ 6 -f 1 -b -o ${BAM_PREFIX}.Paired.FC.bam ${BAM_PREFIX}.Final.bam\n";
		if ($DoneWasp == 0) {
			system ("samtools view -\@ 6 -f 1 -b -o ${BAM_PREFIX}.Paired.FC.bam ${BAM_PREFIX}.Final.bam");
			$CODE = __LINE__; &CheckExit;
		}
		print LOG "samtools index -\@ 8 -b ${BAM_PREFIX}.Paired.FC.bam\n";
		if ($DoneWasp == 0) {
			system ("samtools index -\@ 8 -b ${BAM_PREFIX}.Paired.FC.bam");
			$CODE = __LINE__; &CheckExit;
		}
		# Write Single Read file
		print LOG "# Generate FeatureCounts Input Write Single Read file\n";
		print LOG "samtools view -\@ 6 -F 1 -b -o ${BAM_PREFIX}.Single.FC.bam ${BAM_PREFIX}.Final.bam\n";
		if ($DoneWasp == 0) {
			system ("samtools view -\@ 6 -F 1 -b -o ${BAM_PREFIX}.Single.FC.bam ${BAM_PREFIX}.Final.bam");
			$CODE = __LINE__; &CheckExit;
		}
		print LOG "samtools index -\@ 8 -b ${BAM_PREFIX}.Single.FC.bam\n";
		if ($DoneWasp == 0) {
			system ("samtools index -\@ 8 -b ${BAM_PREFIX}.Single.FC.bam");
			$CODE = __LINE__; &CheckExit;
		}
	}
	else {
		# Need to create PE and SE if we are not doing WASP filtering using ${BAM_PREFIX}.${BAM_SUFFIX}.bam
		# Generate FeatureCounts Input
		# Write Paired Read file
		print LOG "# Generate FeatureCounts Input Write Paired Read file\n";
		print LOG "samtools view -\@ 6 -f 1 -b -o ${BAM_PREFIX}.Paired.FC.bam ${BAM_PREFIX}.${BAM_SUFFIX}.bam\n";
		if ($DoneWasp == 0) {
			system ("samtools view -\@ 6 -f 1 -b -o ${BAM_PREFIX}.Paired.FC.bam ${BAM_PREFIX}.${BAM_SUFFIX}.bam");
			$CODE = __LINE__; &CheckExit;
		}
		print LOG "samtools index -\@ 8 -b ${BAM_PREFIX}.Paired.FC.bam\n";
		if ($DoneWasp == 0) {
			system ("samtools index -\@ 8 -b ${BAM_PREFIX}.Paired.FC.bam");
			$CODE = __LINE__; &CheckExit;
		}
		# Write Single Read file
		print LOG "# Generate FeatureCounts Input Write Single Read file\n";
		print LOG "samtools view -\@ 6 -F 1 -b -o ${BAM_PREFIX}.Single.FC.bam ${BAM_PREFIX}.${BAM_SUFFIX}.bam\n";
		if ($DoneWasp == 0) {
			system ("samtools view -\@ 6 -F 1 -b -o ${BAM_PREFIX}.Single.FC.bam ${BAM_PREFIX}.${BAM_SUFFIX}.bam");
			$CODE = __LINE__; &CheckExit;
		}
		print LOG "samtools index -\@ 8 -b ${BAM_PREFIX}.Single.FC.bam\n";
		if ($DoneWasp == 0) {
			system ("samtools index -\@ 8 -b ${BAM_PREFIX}.Single.FC.bam");
			$CODE = __LINE__; &CheckExit;
		}
	}

	# Need to check to see if there are any Paired reads in the ${BAM_PREFIX}.Paired.FC.bam
	# We'll just count the number of records in the Paired file.
	# If this is > 0 then we need to do Paired FeatureCounts below, otherwise we don't need to do PE.
	my $PairedPresent = `samtools view -\@ 8 -c ${BAM_PREFIX}.Paired.FC.bam`;
	chomp $PairedPresent;

	system ("echo \"DONE WASP\" >DoneWASP");


	# FeatureCounts
# Need to add FeatureCounts version into modules
my $FeatureCounts = "/storage/hpc/group/UMAG_test/WORKING/cs744/RNA_seq/code/subread-2.0.3-source/bin/featureCounts";
	# Output file name nomenclature
	# ${BAM_PREFIX}.[V].[PE/SE].[G/E].[MM].[S/U].FC
	# [V]		V=Ensembl GTF version
	# [PE/SE]	PE=Paired, SE=Single
	# [G/E]	G=Gene, E=Exon
	# [MM]	0=MultiMappers Excluded, 1=MultiMappers Included
	# [S/U]	0=Unstranded, 1=Stranded, 2=reversely stranded

	system ("mkdir -p tmpFC");
	my $strand = 0;
	my $mm = 0;
	my $type = "SE";
	while ($strand <= 2) { 
		while ($mm <= 1) {
			if ($PairedPresent > 0) {
				$type = "PE";
				if ($mm == 0) {
					# Paired, Gene, 0=MultiMappers Excluded, -s 0 UNSTRANDED
					push @FC_jobs, "$FeatureCounts -T 4 -d 35 -p --countReadPairs -F GTF -O --fraction -s $strand -a $GTFfile --tmpDir tmpFC -o ${BAM_PREFIX}.$AnnotationVersion.$type.G.$mm.$strand.FC ${BAM_PREFIX}.Paired.FC.bam";
					# Paired, Exon, 0=MultiMappers Excluded, -s 0 UNSTRANDED
					push @FC_jobs, "$FeatureCounts -T 4 -d 35 -p --countReadPairs -f -g exon_id -F GTF -O --fraction -s $strand -a $GTFfile --tmpDir tmpFC -o ${BAM_PREFIX}.$AnnotationVersion.$type.E.$mm.$strand.FC ${BAM_PREFIX}.Paired.FC.bam";
				}
				else {
					# Paired, Gene, 0=MultiMappers Excluded, -s 0 UNSTRANDED
					push @FC_jobs, "$FeatureCounts -T 4 -d 35 -p --countReadPairs -F GTF -M -O --fraction -s $strand -a $GTFfile --tmpDir tmpFC -o ${BAM_PREFIX}.$AnnotationVersion.$type.G.$mm.$strand.FC ${BAM_PREFIX}.Paired.FC.bam";
					# Paired, Exon, 0=MultiMappers Excluded, -s 0 UNSTRANDED
					push @FC_jobs, "$FeatureCounts -T 4 -d 35 -p --countReadPairs -f -g exon_id -M -F GTF -O --fraction -s $strand -a $GTFfile --tmpDir tmpFC -o ${BAM_PREFIX}.$AnnotationVersion.$type.E.$mm.$strand.FC ${BAM_PREFIX}.Paired.FC.bam";
				}
			}
			$type = "SE";
			if ($mm == 0) {
				# Single, Gene, 0=MultiMappers Excluded, -s 0 UNSTRANDED
				push @FC_jobs, "$FeatureCounts -T 4 -d 35 -F GTF -O --fraction -s $strand -a $GTFfile --tmpDir tmpFC -o ${BAM_PREFIX}.$AnnotationVersion.$type.G.$mm.$strand.FC ${BAM_PREFIX}.Single.FC.bam";
				# Single, Exon, 0=MultiMappers Excluded, -s 0 UNSTRANDED
				push @FC_jobs, "$FeatureCounts -T 4 -d 35 -f -g exon_id -F GTF -O --fraction -s $strand -a $GTFfile --tmpDir tmpFC -o ${BAM_PREFIX}.$AnnotationVersion.$type.E.$mm.$strand.FC ${BAM_PREFIX}.Single.FC.bam";
			}
			else {
				# Single, Gene, 0=MultiMappers Excluded, -s 0 UNSTRANDED
				push @FC_jobs, "$FeatureCounts -T 4 -d 35 -F GTF -M -O --fraction -s $strand -a $GTFfile --tmpDir tmpFC -o ${BAM_PREFIX}.$AnnotationVersion.$type.G.$mm.$strand.FC ${BAM_PREFIX}.Single.FC.bam";
				# Single, Exon, 0=MultiMappers Excluded, -s 0 UNSTRANDED
				push @FC_jobs, "$FeatureCounts -T 4 -d 35 -f -g exon_id -F GTF -M -O --fraction -s $strand -a $GTFfile --tmpDir tmpFC -o ${BAM_PREFIX}.$AnnotationVersion.$type.E.$mm.$strand.FC ${BAM_PREFIX}.Single.FC.bam";
			}
			$mm++;
		}
		$strand++;
	}

	#####
	# Run FeatureCounts in SEMAPHORES
	my $FCjobs = @FC_jobs;
	my $FCSem = 1;
	if (int($Cpu_Node / 4) > 1 ) {
		$Cpu_FC = 4;
		$FCSem = int($Cpu_Node / 4);
	}

	$semFC = Thread::Semaphore->new($FCSem);
	my @FCThreads;

	foreach (@FC_jobs) {
		$semFC->down;
		$t = threads->new(\&FeatureCounts, $_);
		push(@FCThreads,$t);
		sleep 1;
	}
	foreach (@FCThreads) { my $num = $_->join; }
	#
	#####


	# List all the FeatureCount files and push *FC.gz and *FC.summary into @FilesToCopy 
	system ("ls *.FC > FC.list");
	open TMP, "<FC.list";
	while (<TMP>) {
		chomp $_;
		push @FilesToCopy, "${_}.gz";
		push @FilesToCopy, "${_}.summary";
	}
	close TMP;

	# Compress all the FeatureCounts files
	print LOG "# Compressing FeatureCounts\n";
	print LOG "pigz -9 -p4 *.FC\n";
	system ("pigz -9 -p4 *.FC");

#############

# ADD SJ to BED code here
# NEED TO ADD THE FILE NAME FROM THE SJ to BED CODE to the copy logic


=pod
# Code for the conversion from STAR's SJ.out.tab file to a BED12 format file with .junc added to the end. 
modified from awk script from alex dobin https://github.com/alexdobin/STAR/blob/master/extras/scripts/sjBED12.awk and https://gist.github.com/fabiolib/ffb21853e3eb3780150074aeffc54901

STAR OUTPUT SJ.out.tab Column Description
INPUT FOR CONVERSION
column 1: chromosome
column 2: first base of the intron (1-based)
column 3: last base of the intron (1-based)
column 4: strand (0: undefined, 1: +, 2: -)
column 5: intron motif: 0: non-canonical; 1: GT/AG, 2: CT/AC, 3: GC/AG, 4: CT/GC, 5:AT/AC, 6: GT/AT
column 6: 0: unannotated, 1: annotated in the splice junctions database. Note that in 2-pass mode, junctions detected in the 1st pass are reported as annotated, in addition to annotated junctions from GTF.
column 7: number of uniquely mapping reads crossing the junction
column 8: number of multi-mapping reads crossing the junction
column 9: maximum spliced alignment overhang


BED12 Format Column Descriptions as SJ.out.tab.junc files (This is a modified BED12 format for what leafCutter will read)
OUTPUT FROM CONVERSION AND INPUT FOR LEAFCUTTER
column 1: chromosome
column 2: Junction Start (Intron Start)
column 2: Junction End (Intron End)
column 4: Junction Number
column 5: count per Junction
column 6: strand Either "." (=no strand) or "+" or "-".
column 7: ThickStart (this column is not used by leafCutter but has a different function in standard BED12 format so needs to be included for leafCutter to properly read the file)
column 8: ThickEnd (this column is not used by leafCutter but has a different function in standard BED12 format so needs to be included for leafCutter to properly read the file)
column 9: itemRgb (all are set to 255,0,0. this column is not used by leafCutter but has a different function in standard BED12 format so needs to be included for leafCutter to properly read the file) 
column 10: blockCount The number of blocks (exons) in the BED line.
column 11: blockSizes (from Alex Dobin's Awk Script both are set to be column 9 (maximum spliced alignment overhang need) from STAR output SJ.out.tab.)
column 12: blockStarts (from Alex's Awk Script the first value is set as 0 and the second is calculated as End-Start+(maximum spliced alignment overhang need)+1.

Outlined steps for conversion
In the SJ.out.tab file the 4th column identifies the strand (0: undefined, 1: +, 2: -). If the 4th column is - strand then the new line results will be printed to the .bed12 file. 
Column 1 will be the chromosome which is column 1 in the SJ.out.tab file. 
Column 2 will be the intron start site. This is calculated from the second and ninth colums in the SJ.out.tab. The start minus the overhang minus 1. 
Column 3 is the intron end site. This is the end (column 3 SJ.out.tab) plus the overhang (column 9 SJ.out.tab). 
Column 4 is the junction identifier. It is simpley JUNC000 and then the next numerical number. 
Column 5 is the reads supporting the junction. This is found in column 7 of the SJ.out.tab file. 
Column 6 is the strand, which was already identified in the if statement as -. 
Columns 7 and 8 are the think start and think end which are calculated the same as the start and end from before. 
Column 9 is to identify the color if this was to be used in IGV, Included so LeafCutter will read the file.
Column 10 identifies that there are 2 parts to this feature. In this case that there are two exons either side of the junction. 
Column 11 is the block size. From what I can tell from the two sites mentioned above it is equal to the read overhang found in column 9 of the SJ.out.tab. 
Column 12 is the block starts relative to the junction. So the first value is 0 as it is the start relative to the junction and the second value is calculated as the intron end (column 3 SJ.out.tab) minus intron start calculated earlier. 
Then if the strand is not - the same pattern is repeated but placing + in the sixth column. 

=cut

	my @SJ_input;			# Array with *.SJ.out.tab files to convert to BED12
	my $sj_files = `ls *.SJ.out.tab`;
	chomp $sj_files;
	push @SJ_input, split (/\s+/, $sj_files);

	foreach (@SJ_input) {
		print "# Converting $_ to ${_}.junc\n";
		my $sj_in = $_;
		open (FILE, "<$sj_in");
		$CODE = __LINE__; &CheckExit;
		open (OUT_BED, ">${sj_in}.unsorted");
		# We will write the records with a strand == 0 to the ERR file so we have an accounting of everything
		# see https://groups.google.com/g/rna-star/c/B0Y4oH8ZSOY Strand 0 in splice junctions table
		open (ERR, ">${sj_in}.ERR");
		#Modified from https://gist.github.com/fabiolib/ffb21853e3eb3780150074aeffc54901 and #from alex dobin https://github.com/alexdobin/STAR/blob/master/extras/scripts/sjBED12.awk
		while (<FILE>) {
			my $line = $_;
			chomp $line;
			my @a = split("\t", $line);
			if ($a[3] eq "2") {				#negativly stranded junctions
				my $chromo1 = $a[0];		#chromosome
				my $start1 = $a[1]-$a[8]-1;	#Start of intron
				my $end1 = $a[2]+$a[8];		#End of intron
				my $score1 = $a[6];			#Count of Reads supporting
				my $blockwidth1 = $a[8];
				my $blockstart1 = $a[2]-$a[1]+$a[8]+1;
				print OUT_BED $chromo1 . "\t" . $start1 . "\t" . $end1 . "\tJUNC000" . $. . "\t" . $score1 . "\t-\t" . $start1 . "\t" . $end1 . "\t255,0,0\t2\t" . $blockwidth1 . "," . $blockwidth1 . "\t0," . $blockstart1 . "\n";
			}
			elsif ($a[3] eq "1") {			#positivly stranded junctions							
				my $chromo2 = $a[0];		#chromosome
				my $start2 = $a[1]-$a[8]-1;	#Start of intron
				my $end2 = $a[2]+$a[8];		#End of intron
				my $score2 = $a[6];			#Count of Reads supporting
				my $blockwidth2 = $a[8];
				my $blockstart2 = $a[2]-$a[1]+$a[8]+1;
				print OUT_BED $chromo2 . "\t" . $start2 . "\t" . $end2 . "\tJUNC000" . $. . "\t" . $score2 . "\t+\t" . $start2 . "\t" . $end2 . "\t0,0,255\t2\t" . $blockwidth2 . "," . $blockwidth2 . "\t0," . $blockstart2 . "\n";
			}
			else {
				print ERR "$line\n";
				next;
			}
		}
		#Sorting step to get .junc files in similar to regtools .junc files which is the suggested method by leafCutter, but does not work with the realigned recalibrated BAMs
		print "# Sorting\n";
		system ("sort -V -o ${sj_in}.junc ${sj_in}.unsorted");
		$CODE = __LINE__; &CheckExit;
		close FILE;
		close OUT_BED;
		close ERR;

		push @FilesToCopy, "${sj_in}.junc";
		push @FilesToCopy, "$sj_in.ERR";
	}


############


	$TimeEnd = new Benchmark;
	$TimeDiff = timediff($TimeEnd, $TimeStart);
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber WASP & FeatureCounts\tALL FILES\t", timestr($TimeDiff), "\n";
	&DirectorySize;
	system ("echo \"DONE FeatureCounts\" >DoneFeatureCounts");
}	# closing 3544 if ($Analysis eq "rna") {

sub FeatureCounts {
	print LOG "$_\n";
	$Stage = "$LI $TI FeatureCounts ";
	if ($DoneFeatureCounts == 0) {
		print "$_\n";
		system ("$_");
		$CODE = __LINE__; &CheckExit;
	}
	$semFC->up;
}

#
################################################################################


#=pod
################################################################################
#
# CONVERT BAM TO CRAM 	04/23/2024
if ($DoBam2Cram == 1) {
	$StageNumber++;
	$TimeStart = new Benchmark;
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber SAMTOOLS BAM TO CRAM\tALL FILES\t\t\n";
	$Stage = "$StageNumber SAMTOOLS BAM TO CRAM";
	print LOG "# SAMTOOLS BAM TO CRAM\n";

	if ($DoBQSR == 1) { $BAM_SUFFIX = "realigned.recalibrated"; }
	else { $BAM_SUFFIX = "realigned"; }

	if ($DoneBam2Cram == 1) { print LOG "# SAMTOOLS BAM TO CRAM ALREADY DONE\n"; }
	if (int($Cpu_Node / 8) > 1 ) { $Cpu_Samtools = 8; }

	push (@FilesToCopy, "${BAM_PREFIX}.${BAM_SUFFIX}.cram");
	push (@FilesToCopy, "${BAM_PREFIX}.${BAM_SUFFIX}.cram.md5");
	push (@FilesToCopy, "${BAM_PREFIX}.${BAM_SUFFIX}.cram.crai");
	push (@FilesToCopy, "${BAM_PREFIX}.${BAM_SUFFIX}.cram.crai.md5");

	print LOG "samtools view -\@ $Cpu_Samtools -T ${RefGenome}/${ref}.fa -C -o ${BAM_PREFIX}.${BAM_SUFFIX}.cram ${BAM_PREFIX}.${BAM_SUFFIX}.bam\n";
	print LOG "md5sum ${BAM_PREFIX}.${BAM_SUFFIX}.cram >${BAM_PREFIX}.${BAM_SUFFIX}.cram.md5\n";
	if ($DoneBam2Cram == 0) { 
		system ("samtools view -\@ $Cpu_Samtools -T ${RefGenome}/${ref}.fa -C -o ${BAM_PREFIX}.${BAM_SUFFIX}.cram ${BAM_PREFIX}.${BAM_SUFFIX}.bam"); 
		$CODE = __LINE__; &CheckExit;
		system ("md5sum ${BAM_PREFIX}.${BAM_SUFFIX}.cram >${BAM_PREFIX}.${BAM_SUFFIX}.cram.md5");
		$CODE = __LINE__; &CheckExit;
	}

	print LOG "samtools index -\@ 4 ${BAM_PREFIX}.${BAM_SUFFIX}.cram\n";
	print LOG "md5sum ${BAM_PREFIX}.${BAM_SUFFIX}.cram.crai >${BAM_PREFIX}.${BAM_SUFFIX}.cram.crai.md5\n";
	if ($DoneBam2Cram == 0) { 
		system ("samtools index -\@ 4 ${BAM_PREFIX}.${BAM_SUFFIX}.cram");
		$CODE = __LINE__; &CheckExit;
		system ("md5sum ${BAM_PREFIX}.${BAM_SUFFIX}.cram.crai >${BAM_PREFIX}.${BAM_SUFFIX}.cram.crai.md5");
		$CODE = __LINE__; &CheckExit;
	}

	$TimeEnd = new Benchmark;
	$TimeDiff = timediff($TimeEnd, $TimeStart);
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber SAMTOOLS BAM TO CRAM\t${BAM_PREFIX}.${BAM_SUFFIX}.cram\t", timestr($TimeDiff), "\n";
	&DirectorySize;
	system ("echo \"DONE Bam2Cram\" >DoneBam2Cram");
}

#
################################################################################
#=cut

###############################################################################
# COPY FILES

#####
# Check to make sure all the target directories are present and if they don't exist create them. 
# This way we can create new directory structures here and make sure they propogate when we run a new taxon.

$CopyPath = "/storage/htc/$Lab/results/${TaxonID}/${Analysis}/${InputRef}";
print LOG "# Checking destination directories and creating if needed\n";
print LOG "# $CopyPath\n";

system ("mkdir -p ${CopyPath}/bam");
system ("mkdir -p ${CopyPath}/gvcf");
system ("mkdir -p ${CopyPath}/vcf");
system ("mkdir -p ${CopyPath}/bam/CSV");
system ("mkdir -p ${CopyPath}/bam/FC");
system ("mkdir -p ${CopyPath}/bam/LINKS");
system ("mkdir -p ${CopyPath}/bam/LOG");
system ("mkdir -p ${CopyPath}/bam/MATE_MAPPED");
system ("mkdir -p ${CopyPath}/bam/MATE_UNMAPPED");
system ("mkdir -p ${CopyPath}/bam/METRICS");
system ("mkdir -p ${CopyPath}/bam/PDF");
system ("mkdir -p ${CopyPath}/bam/READS_PER_GENE");
system ("mkdir -p ${CopyPath}/bam/RECAL_REPORT");
system ("mkdir -p ${CopyPath}/bam/RG");
system ("mkdir -p ${CopyPath}/bam/SIZE");
system ("mkdir -p ${CopyPath}/bam/SJ");
system ("mkdir -p ${CopyPath}/bam/SQL");
system ("mkdir -p ${CopyPath}/bam/TIME");
system ("mkdir -p ${CopyPath}/bam/TRIM_SUMMARY");
system ("mkdir -p ${CopyPath}/bam/UNMAPPED");
system ("mkdir -p ${CopyPath}/bam/CALLABLE/SUMMARY");
foreach (@SeqForIndelTargetX) {
	system ("mkdir -p ${CopyPath}/bam/CALLABLE/$_");
	system ("mkdir -p ${CopyPath}/gvcf/$_");
}
#
#####

if ($CopyResults == 1 and $DoneCopyFiles == 0) {
	$StageNumber++;
	$TimeStart = new Benchmark;
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tBEGIN\t$StageNumber COPY TO RESULTS\tALL FILES\t\t\n";
	print "BEGIN $StageNumber COPY TO RESULTS\n";
	print LOG "# COPY TO RESULTS\n";

	print LOG "\n#FilesToCopy\n@FilesToCopy \n";
	foreach (@FilesToCopy) {
		my $Dest;
	# CSV
		if ($_ =~ m/.csv/) { $Dest = "bam/CSV"; }
	# FC
		elsif ($_ =~ m/.FC./) { $Dest = "bam/FC"; }
	# LINKS
		elsif ($_ =~ m/links.sam/) { $Dest = "bam/LINKS"; }
	# LOG
		elsif ($_ =~ m/LOG/) { $Dest = "bam/LOG"; }
	# MATE_MAPPED
		elsif ($_ =~ m/MateMapped/) { $Dest = "bam/MATE_MAPPED"; }
	# MATE_UNMAPPED
		elsif ($_ =~ m/MateUnmapped/) { $Dest = "bam/MATE_UNMAPPED"; }
	# METRICS
		elsif ($_ =~ m/.metrics/i) { $Dest = "bam/METRICS"; }
		elsif ($_ =~ m/system_stats.txt/) { $Dest = "bam/METRICS"; }
	# PDF
		elsif ($_ =~ m/.pdf/) { $Dest = "bam/PDF"; }
	# READS_PER_GENE
		elsif ($_ =~ m/.tab$/) { $Dest = "bam/READS_PER_GENE"; }
	# RECAL_REPORT
		elsif ($_ =~ m/recalibration_report/) { $Dest = "bam/RECAL_REPORT"; }
	# RG
		elsif ($_ =~ m/.RG/) { $Dest = "bam/RG"; }
	# SIZE
		elsif ($_ =~ m/.SIZE/) { $Dest = "bam/SIZE"; }
	# SJ
		elsif ($_ =~ m/.out.tab$/) { $Dest = "bam/SJ"; }
		elsif ($_ =~ m/.junc$/) { $Dest = "bam/SJ"; }
		elsif ($_ =~ m/.out.tab.ERR$/) { $Dest = "bam/SJ"; }
	# SQL
		elsif ($_ =~ m/.sql/) { $Dest = "bam/SQL"; }
	# TIME
		elsif ($_ =~ m/.TIME/) { $Dest = "bam/TIME"; }
	# TRIM_SUMMARY
		elsif ($_ =~ m/.TRIM.SUMMARY/) { $Dest = "bam/TRIM_SUMMARY"; }
	# UNMAPPED
		elsif ($_ =~ m/.Unmapped.bam/) { $Dest = "bam/UNMAPPED"; }
	# GVCF
		elsif ($_ =~ m/.g.vcf./) { 
			# Changed to write the g.vcf files directly to the appropriate chr directory 12/28/2018
			#20172.UNMAPPED.g.vcf.gz
			my @FilePart = split(/\./,$_); 
			$Dest = "gvcf\/@FilePart[1]"; 
		}
		elsif ($_ =~ m/.vcf/) { $Dest = "vcf"; }
		elsif ($_ =~ m/Callable/) { 
			# Added chr sub dir for CALLABLE files directly to the appropriate chr directory
			# ${BAM_PREFIX}.CallableLoci.${_}.bed.gz
			my @FilePart = split(/\./,$_); 
			#CALLABLE/SUMMARY *CallableLoci.summary.txt
			if (@FilePart[2] eq 'summary') { $Dest = "bam/CALLABLE/SUMMARY"; } 
			else { $Dest = "bam/CALLABLE\/@FilePart[2]"; } 
		}
		else { $Dest = "bam"; }

		print LOG "cp $_ ${CopyPath}/${Dest}\n";
		$Stage = "$StageNumber $LI $TI COPY TO RESULTS ${CopyPath}/${Dest}/$_";
		system ("cp $_ ${CopyPath}/${Dest}");
		$CODE = __LINE__; &CheckExit;

		# Verify the md5 after copying to results location
		if ($_ =~ m/md5$/) {
			my ($md5, $md5_file) = split(/\s+/,`cat $_`);
			print LOG "echo \'$md5  ${CopyPath}/${Dest}/$md5_file\' \| md5sum -c -\n";
			$Stage = "$LI $TI Checking md5 for ${CopyPath}/${Dest}/$md5_file";
			system ("echo \'$md5  ${CopyPath}/${Dest}/$md5_file\' \| md5sum -c -\n");
			$CODE = __LINE__; &CheckExit;
		}
	}

	$TimeEnd = new Benchmark;
	$TimeDiff = timediff($TimeEnd, $TimeStart);
	$TimeStamp = timestamp();
	print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\t$StageNumber COPY TO RESULTS\tALL FILES\t", timestr($TimeDiff), "\n";
	&DirectorySize;
	system ("echo \"DONE CopyFiles\" >DoneCopyFiles");
}
###############################################################################
# grab end time for overall process
my $TimeEndAll = new Benchmark;
$TimeDiff = timediff($TimeEndAll, $TimeStartAll);
print TIME "$Analysis\t$LI\t$TI\t$TimeStamp\tEND\tEND\tALL\t", timestr($TimeDiff), "\n";
close TIME;
close LOG;
close SIZE;

###############################################################################
# Kill the stats collector before generating the stats figures.

if ($DoStats == 1) {
	$stats->die;
	print "Generating Hardware stats plot....\n";
	sleep 5;	
	&StatsPlot;
	if ($CopyResults == 1) {
		# COPY STATS pdf
		if ($UnmappedOnly == 0) {
			system ("cp ${BAM_PREFIX}.stats.pdf $CopyPath/bam/PDF/ ");				# 04/25/2021 added PDF subdirectory
			system ("cp ${BAM_PREFIX}.TIME $CopyPath/bam/TIME/ ");					# 05/08/2021 added TIME subdirectory
			system ("cp ${BAM_PREFIX}.command.LOG $CopyPath/bam/LOG/ ");			# 05/08/2021 added LOG subdirectory
			system ("cp ${BAM_PREFIX}.system_stats.txt $CopyPath/bam/METRICS/ ");	# 05/08/2021 added METRICS subdirectory
		}
	}
}

#####
# Now that we're done with everything we delete the run directory
if ($DeleteResults == 1) {
	system ("rm -rf $cwd"); 
	$Stage = "DELETE RUN DIRECTORY $cwd";
	$CODE = __LINE__; &CheckExit;
}

# Send e-mail for completed process
&emailSUCCESS;
exit;

###############################################################################
#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
###############################################################################

sub DirectorySize {
	$DirSize = `du -sb "$cwd" | cut -f1`;
	chomp $DirSize;
	print SIZE "$LI\t$Analysis\t$StageNumber\t$TimeStamp\t$DirSize\n";
}

sub timestamp {
  my $t = localtime;
  return sprintf( "%04d-%02d-%02d %02d:%02d:%02d",
                  $t->year + 1900, $t->mon + 1, $t->mday,
                  $t->hour, $t->min, $t->sec );
}

sub yyyymmdd {
  my $t = localtime;
  return sprintf( "%04d-%02d-%02d",
                  $t->year + 1900, $t->mon + 1, $t->mday );
}

sub CheckExit {
	$ExitCode = $? >> 8;
	if ($? >> 8 != 0) {
		print "failed to execute: $!\n";
		$ExitCode = $? >> 8;
		print "EXIT CODE:$?\t ExitCode:$ExitCode\n";
		$stats->die;
		# Added the stats plot here so that if something dies it generates the plots, send email, then exits 07/09/2018
		if ($DoStats == 1) {
			$stats->die;
			print "Generating Hardware stats plot....\n";
			sleep 5;
			&StatsPlot;
			# COPY STATS pdf
			if ($UnmappedOnly == 0) {
				system ("cp ${BAM_PREFIX}.stats.pdf $CopyPath/bam/ ");
				system ("cp ${BAM_PREFIX}.TIME $CopyPath/bam/ ");
				system ("cp ${BAM_PREFIX}.command.LOG $CopyPath/bam/ ");
				system ("cp ${BAM_PREFIX}.system_stats.txt $CopyPath/bam/ ");
			}
		}
		&emailFAILURE;
		exit;
	}
}

sub emailFAILURE {
	print "!!!! SENDING E-MAIL !!!!\n";
	my $messageFAILURE = Email::MIME->create(
		header_str => [
			From    => "$Email",
			To      => "$Email",
			Subject => "$BAM_PREFIX FAILURE",
		],
		attributes => {
			encoding => 'quoted-printable',
			charset  => 'ISO-8859-1',
		},
		body_str => "$BAM_PREFIX failed on $HostName\nStage: $Stage\nCode: $CODE\n",
	);
sendmail($messageFAILURE);						# send the message
}

sub emailSUCCESS {
	print "!!!! SENDING E-MAIL !!!!\n";
	my $messageSUCCESS = Email::MIME->create(
		header_str => [
			From    => "$Email",
			To      => "$Email",
			Subject => "$BAM_PREFIX COMPLETED",
		],
		attributes => {
			encoding => 'quoted-printable',
			charset  => 'ISO-8859-1',
		},
		body_str => "$BAM_PREFIX COMPLETED processing on $HostName\n",
	);
sendmail($messageSUCCESS);						# send the message
}

sub emailWARNING {
	print "!!!! SENDING WARNING E-MAIL !!!!\n";
	$" = ();	# Set the array delimiter to undefined for printing e-mail
	my $messageWARNING = Email::MIME->create(
		header_str => [
			From    => "$Email",
			To      => "$Email",
			Subject => "$BAM_PREFIX WARNING",
		],
		attributes => {
			encoding => 'quoted-printable',
			charset  => 'ISO-8859-1',
		},
		body_str => "WARNING!!\n$BAM_PREFIX failed QC on $HostName\nStage: $Stage\nYou need to check file $BAM_PREFIX.alignment_summary_metrics OR $BAM_PREFIX.insert_size_metrics\n@QCwarnings\n",
	);
sendmail($messageWARNING);						# send the message
}

sub HyperThread {
	my $Chip = `lscpu | grep -i -E \"^Vendor ID:\"`;
	my $CPU = `lscpu | grep -i -E  \"^CPU\\(s\\):\" | grep -o \'[0-9]*\'`;
	my $Threads = `lscpu | grep -i -E  \"^Thread\\(s\\) per core:\"| grep -o \'[0-9]*\'`;
	my $Cores = `lscpu | grep -i -E  \"^Core\\(s\\) per socket:\"| grep -o \'[0-9]*\'`;
	my $Sockets = `lscpu | grep -i -E  \"^Socket\\(s\\):\"| grep -o '[0-9]*\'`;
	chomp ($Chip, $CPU, $Threads, $Cores, $Sockets);
	if ($Chip =~ m /AMD/i or $Chip =~ m/Intel/i) {
		if ($Chip =~ m /AMD/i) { $HT = "OFF"; }
		elsif ($Chip =~ m /Intel/i and $Threads == 1) { $HT = "OFF"; }
		else { $HT = "ON"; }
	}
	else { $HT = "UNK"; }
	return $HT;
}

sub Memory {
	# Determine the total amount of memory on the node. Added 06/04/2019
	my $RAM = `cat /proc/meminfo | grep -e \"MemTotal:\"`;
	chomp ($RAM);
	$RAM =~ s/MemTotal:\s+//;
	$RAM =~ s/\s+kB//;
	$MemTotal = floor($RAM / 1024 / 1024);
	return $MemTotal;
}

sub StatsPlot {
	# READ IN times and assign to hashes based on program
	open IN, "${BAM_PREFIX}.TIME";
	my %Start = ();
	my %Stop = ();
	while (<IN>) {
		next if ($_ =~ m/^#/);	# Discard header
		chomp $_;
		# ORIGINAL 1717	2015-09-20 08:20:22	END	TRIMMOMATIC	ALL FILES	1168 wallclock secs ( 0.78 usr  0.39 sys + 8412.99 cusr 1364.30 csys = 9778.46 CPU)
		# Changed TIME format to add analysis and tissue 08/10/2019 
		# $Analysis $lab_id $tissue_id ...
		# atac    9999999 9999999 2019-08-11 10:33:25     BEGIN   1 TRIMMOMATIC   ALL FILES
		my ($analysis,$lab_id,$tissue_id,$timestamp,$StartEnd,$Program,$files,$time) = split(/\t/,$_);
		if ($StartEnd eq "BEGIN") { $Start{$Program} = "$timestamp"; }
		elsif ($StartEnd eq "END") { $Stop{$Program} = "$timestamp"; }
		#$hash{ $key } = $value;      # hash, using variables
	}
	close IN;
	my @Start;
	my @Stop;
	#foreach my $key (sort {lc $a cmp lc $b} keys %Start) {
	foreach my $key (sort { $a <=> $b } keys %Start) {
		#print "START: $key\t$Start{$key}\n";
		unless ($key eq "ALL") {push (@Start, "$key\t$Start{$key}")};
	}
	#foreach my $key (sort {lc $a cmp lc $b} keys %Stop) {
	foreach my $key (sort { $a <=> $b } keys %Stop) {
		#print "STOP: $key\t$Stop{$key}\n";
		unless ($key eq "ALL") {push (@Stop, "$key\t$Stop{$key}")};
	}
	my $LenStart = @Start;
	my $LenStop = @Stop;
	if ($LenStart != $LenStop) {
		print "Start/Stop arrays of different length\n";
		print "START:$LenStart\tSTOP:$LenStop\n";
		&emailFAILURE;
		exit;
	}
	my @Range;
	my $i = 0;
	while ($i < $LenStart) {
		push (@Range, "$Start[$i]\t$Stop[$i]");
		open "DATA${i}", ">${BAM_PREFIX}.data.${i}.txt";	
		#open "OUTF${_}", ">${input}.${_}.1.FASTA";
		$i++;
	}
	foreach (@Range) { print "$_\n"; }
	# READ IN stats and assign to hashes based on timestamp
	open IN, "${BAM_PREFIX}.system_stats.txt";
	my %time = ();
	while (<IN>) {
		next if ($_ =~ m/^#/);	# Discard header
		chomp $_;
		#HOST	TIME	CPU_U	CPU_S	CPU_T	CACHE	DIRTY	WAIT	READA	WRITEA
		if ($DoIO == 1) {
			my ($Host,$timestamp,$cpu_u,$cpu_s,$cpu_t,$cache,$dirty,$wait,$reada,$writea) = split(/\t/,$_);
			$time{$timestamp} = "$cpu_u,$cpu_s,$cpu_t,$cache,$dirty,$wait,$reada,$writea";
			#$hash{ $key } = $value;      # hash, using variables
		}
		else {
			my ($Host,$timestamp,$cpu_u,$cpu_s,$cpu_t,$cache,$dirty,$wait) = split(/\t/,$_);
			$time{$timestamp} = "$cpu_u,$cpu_s,$cpu_t,$cache,$dirty,$wait";
		}
	}
	close IN;
	open OUT, ">${BAM_PREFIX}.gp.data";
	my $Start = ();
	my $End = ();	
	$i = 0;
	while ($i < $LenStart) {
		my ($StageStart,$StartTime,$StageEnd,$EndTime) = split(/\t/,$Range[$i]);	
		#my $StartTime	= "2015-09-20 08:00:54";
		#my $EndTime	= "2015-09-21 01:08:08";
		print "STARTTIME:$StartTime\tENDTIME:$EndTime\n";	
		while ( my ($timestamp, $value) = each(%time) ) {
			my $Start = Date_Cmp($timestamp,$StartTime);	#date1<date2->-1 date1=date2->0 date1>date2->1
			my $End = Date_Cmp($timestamp,$EndTime);	#date1<date2->-1 date1=date2->0 date1>date2->1
			if ($Start >= 0 and $End <= 0) {	
				#print "$timestamp => $value\n";
				if ($DoIO == 1) {
					my ($cpu_u,$cpu_s,$cpu_t,$cache,$dirty,$wait,$reada,$writea) = split(/,/,$value);
					print {"DATA${i}"} "$timestamp\t$cpu_u\t$cpu_s\t$cpu_t\t$cache\t$dirty\t$wait\t$reada\t$writea\n";
				}
				else {
					my ($cpu_u,$cpu_s,$cpu_t,$cache,$dirty,$wait) = split(/,/,$value);
					print {"DATA${i}"} "$timestamp\t$cpu_u\t$cpu_s\t$cpu_t\t$cache\t$dirty\t$wait\n";
				}
			}
		}
	$i++;
	}

	$i = 0;
	while ($i < $LenStart) {
		close ("DATA${i}");
		$i++;
	}
	open GP, ">${BAM_PREFIX}.gp.txt";
	print GP "set datafile separator \"\t\" \n";
	print GP "set terminal pdfcairo size 7,5  \n";
	print GP "set output '${BAM_PREFIX}.stats.pdf'  \n";
	print GP "set key out horiz bot center \n";
	print GP "set xdata time  \n";
	print GP "set timefmt \"%Y-%m-%d %H:%M:%S\"  \n";
	print GP "set xtics rotate scale 0.25 autofreq \n";
	print GP "set format x \"%H:%M\" \n";
	print GP "set xlabel 'TimeStamp HH:MM'  \n";
	print GP "set autoscale x  \n";
	print GP "set autoscale y  \n";
	if ($DoIO == 1) {
		print GP "set autoscale y2  \n";
		print GP "set ylabel '\%CPU & \%wa x10'  \n";
		print GP "set y2label 'I/O MB/s'  \n";
		print GP "set y2tics autofreq \n";
	}
	else { print GP "set ylabel '\%CPU & \%wa x10  \n"; }

	$i = 0;
	while ($i < $LenStart) {
		my ($StageStart,$StartTime,$StageEnd,$EndTime) = split(/\t/,$Range[$i]);
		print GP "set title '${BAM_PREFIX} $StageStart' \n";
		if ($DoIO == 1) {
			print GP "plot '${BAM_PREFIX}.data.${i}.txt' using 1:2 with points pt 6 ps 0.4 axes x1y1 title \"$StageStart CPU\", \\\n";
			print GP "'${BAM_PREFIX}.data.${i}.txt' using 1:8 with points pt 6 ps 0.4 axes x1y2 title \"$StageStart Read\", \\\n";
			print GP "'${BAM_PREFIX}.data.${i}.txt' using 1:9 with points pt 6 ps 0.4 axes x1y2 title \"$StageStart Write\", \\\n";
			print GP "'${BAM_PREFIX}.data.${i}.txt' using 1:(\$7*10) with points pt 6 ps 0.4 axes x1y1 title \"$StageStart \%wa\" \n";
		}
		else {
			print GP "plot '${BAM_PREFIX}.data.${i}.txt' using 1:2 with points pt 6 ps 0.4 axes x1y1 title \"$StageStart CPU\", \\\n";
			print GP "'${BAM_PREFIX}.data.${i}.txt' using 1:(\$7*10) with points pt 6 ps 0.4 axes x1y1 title \"$StageStart \%wa\" \n";
		}
		print GP "#\n";
		$i++;
	}
	print GP "exit  \n";
	close GP;
	system ("$Gnuplot <${BAM_PREFIX}.gp.txt");
}

sub AlignmentSummary {
	# ALIGNMENT SUMMARY METRICS
	# Added 05/30/2019
	# Concatenate the unmapped and mapped so we can process them together and capture the number of unmapped reads
	# This will result in two sections in the csv file that is uploaded to db.
	# The unmapped will have zeros for everything except the read counts
	system ("cat ${BAM_PREFIX}.alignment_summary_metrics ${BAM_PREFIX}.Unmapped.alignment_summary_metrics >${BAM_PREFIX}.TMP.alignment_summary_metrics");
	$" = ',';
#	open IN, "<${BAM_PREFIX}.alignment_summary_metrics";
	open IN, "<${BAM_PREFIX}.TMP.alignment_summary_metrics";
	open OUT, ">${BAM_PREFIX}.alignment_summary_metrics.csv";
	while (<IN>) {
		if ($_ =~ m/^CATEGORY/) {
			chomp $_;
			@header = split(/\s/,$_);
			push @header,"qc_flag";				# Add a column for the QC_FLAG that we assign below
			unshift @header,"run_date";			# Add a column for the run date timestamp
			unshift @header,"input_ref";		# Add a column for the reference genome used 	05/31/2019
			unshift @header,"tissue_id";		# Add a column for the tissue_id				04/27/2021
			unshift @header,"lab_id";			# Add a column for the lab_id
			my @lc_header = map { lc } @header;
			print OUT "@lc_header\n";
		}		
		chomp $_;
		@fields = split(/\s/,$_);
		$QCflag = ();
		# For some reason picard prints a block where the sample,library and read_group are null
		# and then a second block where these fields are populated. So we skip the first block
		# if the sample is null. 
		# next if $fields[24] =~ m//; Added this 09/25/2019 but it broke this so fixed with line below on 12/05/2019
		if ($fields[24] =~ m/\d+/) {

			# Picard v2.17.10 added two columns to the output [18]PF_READS_IMPROPER_PAIRS,[19]PCT_PF_READS_IMPROPER_PAIRS
			# which shifted the array positions of the fields that we want
			# [0]CATEGORY,[1]TOTAL_READS,[2]PF_READS,[3]PCT_PF_READS,[4]PF_NOISE_READS,[5]PF_READS_ALIGNED,[6]PCT_PF_READS_ALIGNED
			# [7]PF_ALIGNED_BASES,[8]PF_HQ_ALIGNED_READS,[9]PF_HQ_ALIGNED_BASES,[10]PF_HQ_ALIGNED_Q20_BASES,[11]PF_HQ_MEDIAN_MISMATCHES
			# [12]PF_MISMATCH_RATE,[13]PF_HQ_ERROR_RATE,[14]PF_INDEL_RATE,[15]MEAN_READ_LENGTH,[16]READS_ALIGNED_IN_PAIRS
			# [17]PCT_READS_ALIGNED_IN_PAIRS,[18]PF_READS_IMPROPER_PAIRS,[19]PCT_PF_READS_IMPROPER_PAIRS,[20]BAD_CYCLES
			# [21]STRAND_BALANCE,[22]PCT_CHIMERAS,[23]PCT_ADAPTER,[24]SAMPLE,[25]LIBRARY,[26]READ_GROUP

			if ($fields[6] > 0 and $fields[6] <= 0.90) { $QCflag = 1; push (@QCwarnings, "PCT_PF_READS_ALIGNED:\t$fields[0]\t$fields[6]\tLIBRARY:\t$fields[25]\n"); }						# PCT_PF_READS_ALIGNED is too low
			if ($fields[19] >= 0.05 and $fields[19] <= 0.45) {$QCflag = 1; push (@QCwarnings, "PCT_PF_READS_IMPROPER_PAIRS:\t$fields[0]\t$fields[19]\tLIBRARY:\t$fields[25]\n"); }			# PCT_PF_READS_IMPROPER_PAIRS is too high
			if ($fields[21] >= 0.55 or ($fields[21] > 0 and $fields[21] <= 0.45)) {$QCflag = 1; push (@QCwarnings, "STRAND_BALANCE:\t$fields[0]\t$fields[21]\tLIBRARY:\t$fields[25]\n"); }	# STRAND_BALANCE is too high
			if ($fields[22] >= 0.05) { $QCflag = 1; push (@QCwarnings, "PCT_CHIMERAS:\t$fields[0]\t$fields[22]\tLIBRARY:\t$fields[25]\n"); } 												# PCT_CHIMERAS is too high
			if ($fields[23] >= 0.001) { $QCflag = 1; push (@QCwarnings, "PCT_ADAPTER:\t$fields[0]\t$fields[23]\tLIBRARY:\t$fields[25]\n"); }												# PCT_ADAPTER is too high
			# Added $InputRef so that we can keep stats for multiple runs in the same table 05/31/2019
			# Added $TI for RNAseq data 04/27/2021
			print OUT "$LI,$TI,$InputRef,$TimeStamp,@fields,$QCflag\n";	
		}
	}
	if ($QCflag == 1) { &emailWARNING; }
	close IN;
	close OUT;
}

sub InsertSummary {
	##############################
	# INSERT SUMMARY METRICS
	$" = ',';
	open IN, "<${BAM_PREFIX}.insert_size_metrics";
	open OUT, ">${BAM_PREFIX}.insert_size_metrics.csv";
	$QCflag == 0;
	#@header = ();
	#@lc_header = ();

	while (<IN>) {
		if ($_ =~ m/^MEDIAN_INSERT_SIZE/) {
			chomp $_;
			@header = split(/\s/,$_);
			push @header,"qc_flag";				# Add a column for the QC_FLAG that we assign below
			unshift @header,"run_date";			# Add a column for the run date timestamp
			unshift @header,"input_ref";		# Add a column for the reference genome used 	05/31/2019
			unshift @header,"tissue_id";		# Add a column for the tissue_id				04/27/2021
			unshift @header,"lab_id";			# Add a column for the lab_id
			my @lc_header = map { lc } @header;
			print OUT "@lc_header\n";
		}		
		next if $_ =~ m/^#|^\n|^MEDIAN_INSERT_SIZE/;	# Comment lines start with '#'
		last if $_ =~ m/^insert_size/;					# Comment lines start with '#'

		chomp $_;
		@fields = split(/\s/,$_);
		$QCflag = ();
		#	0 MEDIAN_INSERT_SIZE, 1 MEDIAN_ABSOLUTE_DEVIATION, 2 MIN_INSERT_SIZE, 3 MAX_INSERT_SIZE, 4 MEAN_INSERT_SIZE, 5 STANDARD_DEVIATION
		#	6 READ_PAIRS, 7 PAIR_ORIENTATION, 8 WIDTH_OF_10_PERCENT, 9 WIDTH_OF_20_PERCENT, 10 WIDTH_OF_30_PERCENT, 11 WIDTH_OF_40_PERCENT,
		#	12 WIDTH_OF_50_PERCENT, 13 WIDTH_OF_60_PERCENT, 14 WIDTH_OF_70_PERCENT, 15 WIDTH_OF_80_PERCENT, 16 WIDTH_OF_90_PERCENT,
		#	17 WIDTH_OF_99_PERCENT, 18 SAMPLE,	19 LIBRARY, 20 READ_GROUP

		# Picard v2.17.10 added two columns to the output [1**]MODE_INSERT_SIZE, [18**]WIDTH_OF_95_PERCENT
		# which shifted the array positions of the fields that we want
		# [0]MEDIAN_INSERT_SIZE,[1**]MODE_INSERT_SIZE,[2]MEDIAN_ABSOLUTE_DEVIATION,[3]MIN_INSERT_SIZE,[4]MAX_INSERT_SIZE,[5]MEAN_INSERT_SIZE,[6]STANDARD_DEVIATION
		# [7]READ_PAIRS,[8]PAIR_ORIENTATION,[9]WIDTH_OF_10_PERCENT,[10]WIDTH_OF_20_PERCENT,[11]WIDTH_OF_30_PERCENT,[12]WIDTH_OF_40_PERCENT
		# [13]WIDTH_OF_50_PERCENT,[14]WIDTH_OF_60_PERCENT,[15]WIDTH_OF_70_PERCENT,[16]WIDTH_OF_80_PERCENT,[17]WIDTH_OF_90_PERCENT
		# [18**]WIDTH_OF_95_PERCENT,[19]WIDTH_OF_99_PERCENT,[20]SAMPLE,[21]LIBRARY,[22]READ_GROUP

		# For some reason picard prints a block where the sample,library and read_group are null
		# and then a second block where these fields are populated. So we skip the first block
		# if the sample is null. 
		# next if $fields[20] =~ m/\d+/; Added this 10/28/2020 to check that the [20]SAMPLE field is not null
		if ($fields[20] =~ m/\d+/) {
			if ($fields[6] / $fields[5] >= 0.30) { $QCflag = 1; push (@QCwarnings, "STANDARD_DEVIATION:\t$fields[6]\tMEAN_INSERT_SIZE $fields[5]\tLIBRARY:\t$fields[22]\n"); }	# stdev / mean is too high
			# Added $InputRef so that we can keep stats for multiple runs in the same table 05/31/2019
			# Added $TI for RNAseq data 04/27/2021
			print OUT "$LI,$TI,$InputRef,$TimeStamp,@fields,$QCflag\n";
		}
	}
	if ($QCflag == 1) { &emailWARNING; }
	close IN;
	close OUT;
}

sub CallableLoci {
	# Parse the CallableLoci summary files to create a single file
	# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
	# 04/24/2021 this appears to be broke
	# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
	open OUT, ">${BAM_PREFIX}.CallableLoci.summary.txt";
	foreach (@SeqForIndelTargetX) {
		my $bta = $_;
		my %CallableLoci;
		my @States;
		my @Values;
		my $input = "${BAM_PREFIX}.CallableLoci.${bta}.summary.txt";
		open IN, "<$input";
		while (<IN>) {
			chomp $_;
			$_ =~ s/^\s+//;	
			next if $_ =~ m/^state/;
			my ($State,$nBases) = split(/\s+/,lc $_);
			$CallableLoci{$State} = $nBases;
		}
		# Sort the hash by the state and push into new array
		foreach my $t (sort { lc $a cmp lc $b } keys %CallableLoci) {
			push (@States, $t);
			push (@Values, $CallableLoci{$t});
		}
		unshift @Values, $bta;
		unshift @Values, $LI;
		unshift @States, "chr";
		unshift @States, "lab_id";
		# Added chrA1 for cat genome 06/07/2018
#		if ($bta == 1 or lc $bta eq "chr1") { print OUT "@States\n" };
		if ($bta == 1 or lc $bta eq "chr1" or lc $bta eq "chrA1") { print OUT "@States\n" };
		print OUT "@Values\n";
		close IN;
	}
	close OUT;
}

sub ReadsPerGene {
=pod
	# Adapted from CollectFPKM_v0.0.1.pl added 04/24/2021
	# Variables available at this point in the @ReadsPerGene
	# "$TaxonID,$InputRef,$Date,$LI,$TI,$animal_id,$base_file,$lib,$abbrev,${bwa_output}ReadsPerGene.out.tab");

	# Variables we want/need in the @ReadsPerGene array
	# If all of these parts represent each element of the array then we can parse them and process each file
	# and write all the results to one csv file.

	# For RNASEQ application where we are processing all $TI for each $LI to do genotyping we do NOT call this subroutine.
	# We currently check if $TI > 0 on line 488
	# And around line 1234 we only call &ReadsPerGene if the $TI > 0

	# !!!!!!!!!!!!!!!!!! NOTES !!!!!!!!!!!!!!!!!!!!!!!
	# If duplicates are run with --dups then there will be two sets of entries for each set of files
	# However, since we will aggregate these by $LI and $TI to get total counts it shouldn't matter
	# There may be issues if a $TI has a mix of both stranded and unstranded libraries and we aggregate without the $lib
=cut

	open IN, "<${BAM_PREFIX}_ReadsPerGene_input.txt";
	while (<IN>) {
		chomp $_;
		push @ReadsPerGene, $_;
	}
	close IN;
	open RPG, ">${LI}.${TI}.ReadsPerGene.csv";
	# NO HEADER
	# Columns for output file that corresponds to db columns
	# taxon_id,reference_version,run_date,lab_id,tissue_id,international_id,base_file,library,masurca_abbrev,gene_name,count_unstranded,count_positive,count_negative
	# "$TaxonID,$InputRef,$Date,$LI,$TI,$animal_id,$base_file,$lib,$abbrev,$gene,$counts_unstranded,$counts_pos,$counts_neg";

	foreach (@ReadsPerGene) {
		my ($TaxonID,$InputRef,$Date,$LI,$TI,$animal_id,$base_file,$lib,$abbrev,$FileName) = split /\,/,$_;
		open TMP, "<$FileName";
		while (<TMP>) {
			next if ($. <= 4);
			# 4 header lines of ReadsPerGene.out.tab need to be skipped
			# N_unmapped      2371    2371    2371
			# N_multimapping  25814   25814   25814
			# N_noFeature     61176   63469   285402
			# N_ambiguous     3702    1913    68
			# gene32386       3       3       0
			# gene32387       0       0       0
			# gene32388       0       0       0

			chomp $_;
			my ($gene, $counts_unstranded, $counts_pos, $counts_neg) = split /\t/,$_;
			print RPG "${TaxonID},${InputRef},${Date},${LI},${TI},${animal_id},${base_file},${lib},${abbrev},${gene},${counts_unstranded},${counts_pos},${counts_neg}\n";
		}
		close TMP;
		#close ARGV if eof;
	}
	close RPG;

	# SQL to upload the files to rnacounts_[taxon_id]_raw
	open SQL, ">${LI}.${TI}.${Date}_Upload_RNAcounts.sql";
		# Generate SQL to upload the files to rnacounts_[taxon_id]_raw
		print SQL "DO \$\$ BEGIN RAISE NOTICE 'Deleting and uploading lab_id:$LI tissue_id:$TI'; END \$\$;\n"; 
		print SQL "DELETE FROM rnacounts_${TaxonID}_raw \n";
		print SQL "WHERE run_date = \'$Date\' \n";
		print SQL "	AND lab_id = $LI \n";
		print SQL "	AND tissue_id = $TI; \n\n";

		print SQL "COPY rnacounts_${TaxonID}_raw \n";
		print SQL "FROM \'${LI}.${TI}.ReadsPerGene.csv\' \n";
		print SQL "WITH CSV; \n\n";
		close SQL;
=pod
		print SQL "DROP INDEX idx_rnacounts_${taxon_id}_raw_lab_id_tissue_id; \n";
		print SQL "CREATE INDEX idx_rnacounts_${taxon_id}_raw_lab_id_tissue_id \n";
		print SQL "  ON rnacounts_${taxon_id}_raw \n";
		print SQL "  USING btree \n";
		print SQL "  (lab_id, tissue_id); \n";
		print SQL "ALTER TABLE rnacounts_${taxon_id}_raw CLUSTER ON idx_rnacounts_${taxon_id}_raw_lab_id_tissue_id; \n";

		print SQL "CLUSTER rnacounts_${taxon_id}_raw; \n";
		print SQL "ANALYZE rnacounts_${taxon_id}_raw; \n";
		print SQL "DO \$\$ BEGIN RAISE NOTICE 'run VACUUM ANALYZE VERBOSE rnacounts_${taxon_id}_raw'; END \$\$;\n"; 
=cut
}




=pod

############################################################
# CODE TO CHANGE WHEN ADDING NEW GENOMES
# Setup know sites file for BQSR
303	Add new genome info to "${RefGenome}/GENOMES.README"
329 Add new line for Setup know sites file for BQSR
397 Setup $heterozygosity parameter for GATK based on $TaxonID if you don't want to use default
461 EDIT "${RefGenome}/INSTRUMENTS.TXT" if any new sequencing instruments are added
665 Read the dictionary file for the genome reference to pull out the chromosomes and unmapped contig names.
	- This may need to be modified depending on how the chromosomes and contigs are named.
2593 sub CallableLoci
	- If nonstandard chromosome nomenclature make sure $bta will match the first chromosome

############################################################
# CHANGELOG
0.7.2 04/23/2024
-- Added BAM2CRAM
	- For now, we put this after everything is done.
	- When we rewrite the SOP we need to do the Bam2Cram conversion earlier and use cram files throughout the rest of the pipeline.

0.7.1 04/25/2023
-- Added FeatureCounts code
	- This subroutine will start with the final bam file, whether it is realigned and recalibrated or not.
	- NONE of the bam files generated for WASP or FeatureCounts will be kept.
	- We first filter on WASP tags to create a bam file that excludes reads that overlap a variant
		- and that variant causes a different alignment.
	- From the merged WASP filtered bam, we generate two new bams, one with paired and the other with single reads.
	- Feature counts is run twice, once for each of the paired/single bam files.
	- Changed the ${LI}.tissue.bam.list around line 845 to use ${BAM_PREFIX}. This was failing when running HC across all tissues of a LI.


0.7.0 11/01/2022
-- MAJOR CHANGES
-- Begin incorporating WASP filtering for STAR
-- Added --use_star_manifest [0 default old behavior] [1 write single manifest file and align all files at once]
	- With the --use_star_manifest code it is probably best to just always use this.
	- Even if there is only a single set of files, it handles this correctly.
	- This way everything will be run consitently.

0.6.3 03/24/2022
-- Added -XX:+UseParallelGC to all the java calls
0.6.3 01/10/2022
-- L861 Added or $InputRef eq "Amel_HAv3.1.52_hgd_ids" for the STAR transcriptome that used the bee3.1 fasta

0.6.2 04/22/2021 - 06/03/2021
-- MAJOR CHANGES
-- Update to use STAR 2.7.9a
	- This is a big jump in versioning for STAR so need to rewrite parts of this
	- 2.7.9a also incorporates a new feature STARconsensus that needs to be added and tested
	- https://github.com/alexdobin/STAR/blob/master/docs/STARconsensus.md
	- When using STARconsensus only use variants where the reference allele is the *minor allele* in the population!
		- This was tested using the vcf from BQSR and resulted in *significantly* lower mapping rates due to the vast majority of variants in the vcf being rare.
-- Look into 3.2 Mapping multiple files in one run from STAR manual.
	- We may be able to refactor the STAR alignment code to use --readFilesManifest
	- This would allow all of the reads to be aligned together which would be better for the 2nd pass
	- and also properly set the RG. It may also make the subsequent sorting and file handling easier.
-- Need to look into new STAR option --genomeLoad
	- With the way we process multiple fastq files, loading the genome index into RAM and keeping it there during alignment may significantly speed things up.
-- 	Added new destinations READS_PER_GENE,TRIM_SUMMARY,PDF,CSV,SQL,METRICS,RG,SIZE,TIME,LOG 05/08/2021
	- We now copy these files to subdirectories in the BAM results directory.
	- This cuts down on the number of files in the BAM directory and is better organized
-- Added &yyyymmdd subroutine to grab the date in 'YYYY-MM-DD' format
-- Added &ReadsPerGene subroutine to summarize STAR gene counts tables
-- Added Two Ensembl genomes for STAR alignment
	- ensembl_ars1.2.103 which is Ensemble ARS1.2 with Btau5.0.1 Y added with the Y GTF converted
	- ensembl_ars1.2.103.Run8 is same as above but incorporates 190923_ALL.sorted.vcf.gz variants
		- This is the cow BQSR file which may need to be evaluated and use a more restrictive file
		- When tested, this had a much lower mapping rate 32% (with variants) vs 95% (normal).
		- THIS IS DUE to the fact that during the GENOME GENERATE STAGE
		- Haploid replace reference alleles with alternative alleles from VCF File (e.g.consensus allele)						
		- In order to make this work we should really only provide a VCF where the ALT allele is the major allele in cow and the REF allele was the minor allele.
-- Added $TI to &AlignmentSummary and &InsertSummary to add the tissue_id to the csv file that gets uploaded for any analysis that is tissue specific.
	- For non-tissue specific analyses the $TI will be null.
	- Everything run prior to this will not have the $TI column so we'll need to manage that during upload.
-- Removed the $StripeCount and $StripeSize due to changing to Progressive File Layout (PFL) for Lustre 06/03/2021

-- !!!!! ISSUE with the depth of coverage reports for tissue specific analyses. See comment in that section. !!!!!

0.6.1 01/23/2021
-- Added bee3.1 reference 
-- Added a couple of checks for when $DoBQSR == 0 so we don't check to make sure the file is available
	- Needed to add this for when we are processing a new genome/species and need to NOT do BQSR
-- When $DoBQSR was 0 we were not adding the ${BAM_PREFIX}.realigned.bam to the @FilesToCopy
	- This will now copy the ${BAM_PREFIX}.realigned.bam if DoBQSR == 0
	- Added code around line 2100 01/24/2021
-- 04/13/2021 Added code to samtools sort to delete TMP files left over from a previous failed run.
-- 04/19/2021 samtools actually uses ~12% more memory than specified. For example, with 30G/thread and 4 threads
	- it was using up to 132G based on top for a large file. 
	- Therefore, we subtract this 12% factor from the numerator $MemTotal.
-- 04/20/2021 Changed the $JavaMem from 4 to 10 in the Realigner block of code.
	- A couple of samples were running out of java heap memory and we have plenty to spare so just use 10
-- 04/20/2021 Some samples were failing Realigner so added --maxReadsInMemory 300000 [default was 150000]

0.6.0 10/18/2020
-- MAJOR CHANGES
-- Added BWA-MEM2 and code to pickup where left off in case run fails or times out
-- BWA-MEM2
	- Tested BWA-MEM2 bwa-mem2-2.1_x64-linux binaries on 10/18/2020
	- On hpc6 node using 48 cores and one PE fq file it was 40% faster real time compared to 0.7.17
	- Need to rebuild the indexes so we put them in $RefGenome/BWA2 directory
	- Need to handle the different versions of the reference only for BWA

-- Added code to resume failed or timed out sessions
	- Basically, when a stage is done we write a file named 'DONE_[stage name]
	- Then when we start the program we check to see if each of the stage name files are present
		For each stage we set a $DONE_[stage] variable to 1=DONE and 0=NOT DONE
	- Because a lot of ancillary info needed to run the pipeline (i.e. file names) is generated
		in the subroutines for each stage, we add an if/then only for the system call to check
		to see if the stage needs to be run.
-- Need to add the default BQSR file for canfam4 around line 426 UMC_canfam4_BQSR_v3.sorted.vcf.gz (DONE)
-- Added UMAG HPC storage location for results around line 2995
-- 01/19/2021 Added $GATK4 to point to the version 4 jar for the AnalyzeCovariates step of BQSR
	- Updates to R and using the conda environment broke the plotting of the BQSR pdf
	- https://github.com/broadinstitute/gatk/pull/6677 
	- https://developer.r-project.org/Blog/public/2020/02/16/stringsasfactors/index.html

0.5.22 10/17/2020
-- Added code to set the Lustre stripe count and size of the working dir
	- $StripeCount and $StripeSize
	- Based on benchmarking with dd and copying ~300GB files the current optimum
	- seems to be a stripe count of 1 (HPC default is 4) and stripe size of 1m (MB) which is default
-- Now, when we create the dir to process a sample we set the striping info


0.5.21 05/09/2020
-- Added the pig genome Sscrofa11.1	pig11.1	9823/pig11.1
-- Changed how the input files are checked around line 750
	- The previous test was failing silently and not sending an email on failure

0.5.20 01/02/2020
-- The previous setting for adapter trimming were ${AdapterFile}:2:30:10:1:TRUE
	- For X-Ten and NovaSeq data where the reads were entirely adapter they were being missed and ending up in the $LI.MateUnmapped.1.fastq.gz and reverse files.
	  This is because the "Simple" method has a weight of 0.6 for matching bases which means for a 12 nt adapter the max score is 0.6*12=7.2
	  Thus for the simple matching all of the adapter-only reads were failing to be filtered out.
	  changed the "Simple" threshold to 6 and it solved the problem. Implemented in v0.5.20.pl
-- Change the Lustre stripe count on the tmp dir to 1 around line 309. Added 01/07/2020

0.5.19 09/25/2019
-- Based on modifications made to 0.5.18_test
-- Added --useNewAFCalculator to HaplotypeCaller
	- see https://software.broadinstitute.org/gatk/documentation/version-history.php?id=8692&page=3
	- see https://software.broadinstitute.org/gatk/documentation/article?id=7258
-- Tested --emit_original_quals to -BQSR which will increase the BAM size but will save having to reprocess
	data up to BQSR if we want to redo BQSR using the --useOriginalQualities when building the model.
	- Decided not to implement this because it increased bam size by 70-100% which would result 
	  in significant additional storage requirements.
-- Made $Heterozygosity a user defined option on command line.
	- Previously we were setting this based on the taxon_id but this introduced too much complexity
	  based on the directory structure nomenclature so we just make this settable.
-- Added --bqsrBAQGOP command line flag to set the Recalibrator --bqsrBAQGapOpenPenalty
	- The documentation suggests that a value of 30 would be more appropriate for WGS so that is 
	  what was used in previous versions. However, lowering this from the default of 40 scales back the 
	  QV distribution and makes it narrower. Setting to default of 40 made BQSR behave better.
	  Tested at 50 which was probably too much so settled on a value of 45 being optimal for cattle and Bos outgroup.
	- Decided to add this as a variable so that it can be adjusted as needed and based on testing in other species.
-- alignment_summary_metrics.csv prints a block without library info then print blocks with library info.
	- read_group info is also missing from report
	- Added a nextif statement to the subroutine to skip the first block without a sample name.
-- Added logic for $BqsrSize = "ALL" for low coverage samples with bam <10 GB
-- removed -phred33 at the beginning of trimmomatic. This was addressed in 0.5.7 08/26/2018 but apparently made it back in at some point.
	- This was again causing some samples to fail in GATK due to "abnormally high QV"
	- Removed again on 11/04/2019
	- added -phred${InputQV} for trimmomatic because some files were not being recognized properly. Default is 33
-- 12/05/2019 fixed bug in &AlignmentSummary "next if $fields[24] =~ m//;" that was added on 09/25/2019 that caused
	- the csv file to not contain the data.
	- changed this to "if ($fields[24] =~ m/\d+/) {" so that it only prints results for lines containing data 


0.5.18 08/26/2019
-- Added code to skip BQSR
	- This became useful again for new genomes where we do not have a known variant file to do BQSR but we want to process
	  the data to generate g.vcf in order to build it.
	- Added the $BAM_SUFFIX variable. Previously we relied on hard coding this such as "realigned.bam" or "realigned.recalibrated.bam"
	  based on where we were in the pipeline. However, if we skip a step such as BQSR we need to be able to specify the full file names.
	- Therefore, we set the $BAM_SUFFIX at the beginning of the code blocks that need it based on what has already been done.
	- Added an if statement for $DoBQSR to skip the entire BQSR block. --bqsr 0 to skip [default 1]
-- Changed parameters for BQSR
	- --quantizing_levels 24
	- --bqsrBAQGapOpenPenalty 40 (Changing this back to default of 40 from 30 has a profound impact on QV distribution especially in outgroup samples)
-- !! Consider adding --emit_original_quals to -BQSR which will increase the BAM size but will save having to reprocess
	data up to BQSR if we want to redo BQSR using the --useOriginalQualities when building the model.
-- Added MACS2 code for ATAC-seq
	- If anything about MACS2 is changed then will need to change the system call for the python envirnomnet.

0.5.17 08/09/2019
-- Restructure the TIME format to include columns for $TI and $Analysis
	- Previously we only had $LI in the time file. This is a problem for multi-tissue analyses such as RNA and ATAC so we add these.
-- Fixed issue where the merged bam files were not getting deleted.
-- Fixed issue where the ${BAM_PREFIX}.UNMAPPED*.realigned.bam files were not getting deleted.
-- Removed all code related to setting number of semaphores based on hyperthreading.
-- Added section to process ATAC data
	- Because some $LI_$TI have many libraries and we need stats on a per library basis and because MACS2 is not library aware
	  and because samtools view to extract per library takes about 3 hours, we just create individual
	  ${BAM_PREFIX}.${Library}.realigned.recalibrated.bam files that also get copied to the final results directory.
	  Although this is wasteful of space it is the easiest solution right now.
	- Waiting on installation of MACS2 to add the peak calling code.
-- Added code to check that ${RefGenome}/${dictionary}.dict actually has entries aroud line 780
-- Added $CopyResults back to code. This is useful when testing and you don't want to overwrite previous results.
	- Default is to write results to target directory.

0.5.16 06/08/2019
-- Added $CODE to capture line number withing code using __LINE__ and put this before all &CheckExit calls to print if error happens.
-- Significantly changed how the unmapped reads are processed and location.
   - Moved all the unmapped reads code to just after the first bam file is produced.
   - The original code had some of the fastq and bam files indicated as compressed but they were not, this was fixed.
   - Added the -F 0x900 flag to the samtools commands to make sure that we exclude not primary alignment and supplementary alignment
-- Added -l 9 highest compression for final samtools merge to produce realigned.recalibrated.bam
   - samtools merge never uses more than 8 threads so no need to set -@ much higher
   - On a ~14 GB test final bam file, -l 9 only produced a file ~0.5% smaller than default and took 3% longer wall clock time
   - Since this is the final bam file just use the highest compression.

0.5.15 05/31/2019
-- Added $UnmappedOnly to be able to only do the stages to produce the first markdups bam file and extract unmapped reads
0.5.14 05/30/2019
-- Added code to &AlignmentSummary to concatenate Unmapped and mapped alignment_summary_metrics to capture the number of unmapped reads
-- Added $InputRef to &AlignmentSummary and &InsertSummary so that we can keep stats for multiple runs in the same table 05/31/2019
-- Added &Memory
-- Added logic to samtools sort of sam files to take into account total memory on node so that it doesn't run out of memory
   - Setting this to 50G and 4 threads/samtools job and 4 semaphores on hpc5 with 384G RAM was causing OOM and killing the job

0.5.13 03/23/2019
-- Added ensembl_ars1.2.95 reference for STAR alignments
-- Added ensembl_umd3.1.94 reference for STAR alignments
-- Changed $Cpu_SplitNCigar = 2; from 1
-- Changed SplitNcigar java memory from 4 to 10
-- Added code to check for file ${BAM_PREFIX}.insert_size_metrics before calling &InsertSize around line 2300
-- Changed &IndelTarget java memory from -Xmx4g to -Xmx8g because this was failing due to not enough memory for RNAseq

0.5.12 02/12/2019
-- Changed how samtools is called. Previously we relied on loading the module and just used "samtools".
	- In order to allow for testing non-module versions of samtools we replace all these with the $Samtools variable
	- that is defined on line 301
-- Added a "unmapped" lower case to the end of the @SeqForIndelTargetX array because unmapped paired reads were getting lost due to GATK -L operations.

0.5.11 12/26/2018
-- Up to v0.5.10 the PrintReads for the unmapped contigs used the incorrect list file (${BAM_PREFIX}.UNMAPPED.forIndelRealigner.intervals)
	- when it should have used (UNMAPPED_contigs.interval_list) Around line 1990 Changed 12/26/2018 in v0.5.11
-- Changed to write the g.vcf files directly to the appropriate chr directory around line 2420 12/28/2018
-- Changed samtools merge steps from 20 CPU back to 10 because it was never using more than 10 cores

0.5.10 11/29/2018
-- modified how the $KnownSites file for BQSR was assigned near lines 338

0.5.9 09/14/2018
-- 

0.5.8 08/27/2018
-- Added $SortMem to change how much memory is given to samtools sort [default 10]
-   Samtools sort was taking a long time with the default of 10G because files wer spilling to disk.
-   sort_mem option added to CreateSOPrun to make this a variable.
-   Giving samtools sort too much memory may result in OOM failure for some files. However, if these fail just
-   rerun using less memory. A good starting point is 100G on machines with 512G RAM. On machines with 384G RAM set to something smaller like 75 or 50.
-	Generally files that will need this much means that there are very few of them and probably shouldn't OOM.
-	If there are a lot of files and thus semaphores then they probably are smaller and will not use as much memory.

0.5.7 08/26/2018
-- Added MINLEN:35 to the beginning of Trimmomatic commands
-   If the input reads were less than the MINLEN and adapter trimming is invoked, this was throwing an error.
-   This typically happens when the data have already been through some form of QC such as adapter or QV trimming.
-   Previously we dealt with this for UMC data by specifying not doing adapter trimming for previously QCd data.
-   However, some SRA samples had already been QCd and were failing.
-   Per email from Tony Bolger on 08/23/2018, by placing MINLEN=35 at the beginning of the command string
-   it should simply exclude read(s) that are less than MINLEN since the operations are serial in the order they are presented.
-   This modifications means that we can now do ILLUMINACLIP trimming on previously trimmed files and the default should be to do trimming.
-- Removed -phred33 from Trimmomatic commands and added TOPHRED33 at the beginning
-   Some samples may not be phred33 and by having the -phred33 flag the QV were not converted which caused GATK errors downstream.
-   This will cause trimmomatic to autmatically detect the QV encoding and if it is not phred33 convert to phed33
-- Added some logic when checking the instrument type to make sure that the instrument specified in the input file
-   is present in the INSTRUMENTS.TXT file. If the specified $Instrument is not in the INSTRUMENT.TXT file then
-   the program will trigger an email error and exit. 
 
0.5.6 08/19/2018
-- Added &CheckExit during the initial checking whether fastq files are present.
-   This was missing previously and if an input file wasn't present the job would fail silently.
-   Now it should send a failure email with the stage.

0.5.5 05/06/2018 - 07/13/2018 MAJOR CHANGES
-- Added info for new cow assembly ARS-UCD1.2 as 1kbulls_ars1.2
-- Changed the flags passed to DepthOfCoverage to include more coverage threshold bins and added --minBaseQuality 15 --minMappingQuality 30
-   By runing DOC after BQSR and including QV and MQ thresholds the coverage numbers will be lower than before but more accurately represent usable data. 
-- Changed Trimmomatic parameters 
-	FROM: LEADING:20 TRAILING:20 SLIDINGWINDOW:4:20 AVGQUAL:20
-	TO:   LEADING:20 TRAILING:20 SLIDINGWINDOW:3:15 AVGQUAL:20
-- Fixed parentheses problem with semaphore calculation when hyperthreading is on
-- Added third plot for BQSR that plots both the before and after in one plot. This is in addition to the before/after.
-- Added code around 1785 to determine the BQSR interval size to use based on the size of the BAM file
-- Added -nct back to the unmapped contig section for HaplotypeCaller. Now that we are using smaller chunks of 50 contigs, this works fine
-   and reduces the run time significantly.
-- Fixed thresholds in &AlignmentSummary for raising warnings
-- Update code related to reference files and chromsome naming to accomodate CFA9.0 where chr are named chrA1..chrF2, chrA1_random_ctg382, chrUn_ctg1801
-- Added check around 520 to make sure that there is an international_id for each line in the input file
-- Change the IndelRealigner to use one semaphore for Unmapped and split the unmapped into chunks
-   Removed the --bam-compression 0 from IndelRealigner output
-   Change the number of CPU for IndelRealigner from 4 to 2 to run more semaphores. 
-   !!!!!!! NEED TO CHECK STATS to make sure it is appropriate !!!!!!! 
-   Need to check the stats output to see if 2 CPU is appropriate given the compression and potential increaste I/O due to more semaphores
-- Added $SOPversion to the list of input options and print this to the log file
-- Changed the number of CPU used for BWA if hyperthreading is on to $Cpu_Align = ($Cpu_Node - 1) * 2
-   On Intel chips with hyperthreading ON BWA will max the %CPU if you double the number threads given to it.
-   !!!!!!! NEED TO CHECK STATS to make sure it is appropriate !!!!!!! 
-- Changed how intermediate files are deleted
-   Previously we were keeping intermediate files for two stages after they were created. This caused the storage to increase substantially.
-   Changed this to delete the previousl intermediate files as soon as the current stage completes successfully.
-   This saves significant storage space for running stuff on HPC storage.
-- Changed the &CheckExit behavior to generate stats plot, email, then exit
-   Previously when an exit error was encountered it just emailed the failure then exited.
-   This meant that we only got the StatsPlot for a complete run. Now when an exit error is encountered we generate this plot, email, then exit.
-- Reworked the IndelRealigner stage. The unmapped contigs were going really slow.
-   For the unmapped contigs, added a second semaphore routine within the main one.
-   This will use one of the original threads to spawn off no more than 8 Realigner threads just for the unmapped contigs.
-   Adding more than 8 sub threads consistently crashed the program on the test sample.
-   If it crashes at this stage with more data then revisit tuning this.

0.5.3 05/06/2018
-- Added Trimmomatic v0.38 -summary option for outputing trim summary file

0.5.1 04/07/2018
-- Added $UseUnique flag to change the $forward and $reverse file names if we are using raw fastq or Unique/Duplicate fastq around line 552
	- 
0.5.0 03/06/2018
- Begin updating and migrating to Lewis
-- Removed all of the options for running individual stages. Now you have to run from start to finish.
-- Added adapter trimming to trimmomatic
   - Changed the --trim 1 option to do Adapter trimming and --trim 0 to skip trimming due to issue with pre-trimmed files 
-- Fixed &AlignmentSummary and &InsertSummary due to the new columns introduced in picard v2.17.10
-- Added variables for each software to accomodate running on Lewis or UMUG
-- Rewrote systemStats_vN.N.N.pl to only collect IO for UMAG hardware so that it will run on Lewis HPC storage
-- Added code to record directory size at the end of each stage and write to $BAM_PREFIX.SIZE
-- Added hashes for instrument and library pixel values to assign the correct optical pixel distance per library for MarkDuplicates

0.4.2 05/24/2017
- fixed some bugs introduced with changes in 0.4.1
-- typo in comparing $Aligner == "STAR" should have been $Aligner eq "STAR"
-- fixed &CheckExit calls for HaplotypeCaller for unmapped reads to add log lines for md5 creation in CombineGVCFs

0.4.1 05/15/2017
- Added ATAC-seq
-- Use 20 Mb regions for BQSR but probably need to chnage this so that the entire genome is used.
-- Need to change the logic for BQSR to check the total amount of data and choose the appropriate region size
- Changed e-mail to use $BAM_PREFIX to account for tissue specific runs

0.4.0 2/03/2017
- Begin adding code for migration to new Lewis infrastructure
- Changed path to lab_id_files.txt around l422
- Changed columns in lab_id_files.txt to include paths to Lewis and MUG

0.3.11 10/13/2016
- Fixed the SAM files not getting deleted
- Added comment lines to the LOG file before each step
- NEED TO FIX .DUP.METRICS line 436

0.3.10 09/01/2016
- Added GATK CallableLoci for wgs analysis
- Added picard CollectMultipleMetrics for all analyses
- Added a $StageNumber iterator so that the stage numbers in the time/log output file are consistent
- changed $Cpu_HC = 6 to $Cpu_HC = 5 in order to get more semaphores to run for HC
- changed HC -XX:ParallelGCThreads=4 to 2
- added the $CopyPath and $Dest variables to use the new directory structure when copying files to final destination
	- NEED TO ADD logic based on hostname to properly set destinations

0.3.8
- Added rna analysis using STAR
############################################################
=cut
