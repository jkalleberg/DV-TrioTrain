# Training Data
These data were used to build the first multi-species-trained DV-AF checkpoint. Each individual has a corresponding set of truth variants (VCF) and truth regions (aka ConfidentRegions, BED format) used by TrioTrain for either training labels or for checkpoint benchmarking after training. Due to file size limitations, these intermediate files are available upon request. However, all of the sequencing data used within the current study are publicly available. The original FASTQ files for all bovine samples can be obtained from NCBI's Sequence Read Archive https://www.ncbi.nlm.nih.gov/sra/. The table below provides a list of all BioSample IDs.

For each chromosome (1...29,X,MT), the raw, multi-sample, compressed and indexed VCFs are available under EVA project accession [PRJEB86883](https://www.ebi.ac.uk/ena/browser/view/PRJEB86883). These multi-sample VCFs were extracted from the larger cohort of 5,612 samples (aka the UMAGv1 cohort) representing multiple bovine species. These data represent all genotypes after VQSR-optimization with the larger cohort, using GATK's HaplotypeCaller (v3.8-1-0-gf15c1c3ef). We include all genotypes -- the high-confidence calls plus filtered calls that were excluded prior to re-training with TrioTrain.



| SRA BioSample ID       | UMAG Lab ID  | Sex   | Mean Coverage | Taxon ID  | Breed                 | Breed Code | Trio Number  | Trio Discordance  | Pedigree  | Test Number   | 
| ---------------------- | ------------ | ----- | ------------- | --------  | -------------         | ---------- | -----------  | ----------------  | --------- | -----------   |
| SAMN10940538	         | 118766       | F     | 23.64         | 9913      | Angus                 | AA         | 1            | 0.11%             | offspring |               |	
| SAMN10940502	         | 32157        | M     | 35.96         | 9913      | Angus                 | AA         | 1            | 0.11%             | father    |               | 
| SAMN10940537	         | 118765       | F     | 23.1          | 9913      | Angus                 | AA         | 1            | 0.11%             | mother    |               | 
| SAMN10598563	         | 199724       | F     | 14.45         | 9913 	    | Hereford              | HE         | 2            | 0.17%             | offspring |               |
| SAMN10598569	         | 199730	    | M     | 17.47         | 9913	    | Hereford              | HE         | 2            | 0.17%             | father    |               | 	
| SAMN10598566	         | 199727       | F     | 12.92         | 9913      | Hereford              | HE         | 2            | 0.17%             | mother    |               |  
| SAMEA4644754	         | 342161	    | F     | 19.1          | 9913      | BrownSwiss            | BS         | 3            | 0.18%             | offspring |               | 
| SAMEA4644756	         | 342163	    | M     | 15.84         | 9913      | BrownSwiss            | BS         | 3            | 0.18%             | father    |               |     
| SAMEA4644755	         | 342162       | F     | 15.14         | 9913      | BrownSwiss            | BS         | 3            | 0.18%             | mother    |               |	
| SAMN15779741           | 342485	    | M	    | 23.66	        | 9913	    | Holstein              | HO	     | 4	        | 0.37%	            | offspring	|               | 
| SAMN15780082	         | 341441	    | M	    | 35.23	        | 9913	    | Holstein	            | HO	     | 4	        | 0.37%	            | father	|               | 
| SAMN15779919	         | 341281	    | F	    | 46.68	        | 9913      | Holstein	            | HO	     | 4	        | 0.37%	            | mother	|               | 
| SAMN10598562	         | 199723	    | F	    | 15.89     	| 9913	    | Hereford  	        | HE	     | 5	        | 0.18%	            | offspring	|               | 
| SAMN10598570	         | 199731	    | M	    | 13.51	        | 9913  	| Hereford	            | HE	     | 5	        | 0.18%	            | father	|               | 
| SAMN10598567	         | 199728	    | F	    | 15.08	        | 9913  	| Hereford	            | HE	     | 5	        | 0.18%	            | mother	|               | 
| SAMEA5159888	         | 342304   	| F	    | 24.9	        | 9913	    | TyroleanGrey	        | TG	     | 6	        | 0.10%	            | offspring	|               | 
| SAMEA5159887	         | 342303	    | M	    | 21.63	        | 9913	    | TyroleanGrey	        | TG	     | 6	        | 0.10%	            | father	|               | 
| SAMEA5159889	         | 342305	    | F	    | 19.77	        | 9913	    | TyroleanGrey	        | TG	     | 6	        | 0.10%	            | mother	|               | 
| SAMN15779593	         | 342472	    | F	    | 50.83	        | 9913	    | HolsteinJersey        | HJ	     | 7	        | 0.14%	            | offspring	|               | 
| SAMN15779644	         | 341035	    | M	    | 39.35	        | 9913	    | HolsteinJersey	    | HJ	     | 7	        | 0.14%	            | father	|               | 
| SAMN15779569	         | 340965	    | F	    | 44.75	        | 9913  	| HolsteinJersey	    | HJ	     | 7	        | 0.14%	            | mother	|               | 
| SAMN15779717	         | 341101	    | M	    | 27.65	        | 9913	    | HolsteinJersey	    | HJ         | 8	        | 0.38%	            | offspring	|               | 
| SAMN15779606	         | 340998	    | M	    | 30.81	        | 9913  	| HolsteinJersey	    | HJ	     | 8	        | 0.38%	            | father	|               | 
| SAMN15779596	         | 342473	    | F	    | 39.31	        | 9913	    | HolsteinJersey	    | HJ	     | 8	        | 0.38%	            | mother	|               | 
| SAMN10598564	         | 199725	    | M	    | 14.79	        | 9913	    | Hereford	            | HE	     | 9	        | 0.44%	            | offspring	|               | 
| SAMN10598569	         | 199730	    | M	    | 17.47	        | 9913	    | Hereford	            | HE	     | 9	        | 0.44%	            | father	|               | 
| SAMN10598565	         | 199726	    | F	    | 14.62	        | 9913	    | Hereford	            | HE	     | 9	        | 0.44%	            | mother	|               | 
| SAMN13655887 	         | 20136	    | F	    | 17.95	        | 9901	    | Bison	                | BI	     | 10	        | 0.27%	            | offspring	|               | 
| SAMN05788493	         | 2406	        | M	    | 22.69	        | 9901	    | Bison	                | BI	     | 10	        | 0.27%	            | father	|               | 
| SAMN13655886	         | 20076	    | F	    | 23.72	        | 9901  	| Bison	                | BI         | 10	        | 0.27%	            | mother	|               | 
| SAMN10940703	         | 20172    	| M	    | 24.06 	    | 9901	    | Bison	                | BI         | 11	        | 0.53%	            | offspring	|               | 
| SAMN05788493	         | 2406	        | M 	| 22.69	        | 9901	    | Bison	                | BI         | 11	        | 0.53%	            | father	|               | 
| SAMN10940702	         | 20098	    | F	    | 23.78	        | 9901	    | Bison	                | BI         | 11	        | 0.53%	            | mother	|               | 
| SAMN08473802	         | 341496	    | M	    | 50.01	        | 30522	    | AngusBrahman	        | F1X   	 | 12	        | 0.64%	            | offspring	| 14            | 
| SAMN08473804	         | 194551	    | M	    | 36.99	        | 9913	    | Angus	                | AA	     | 12	        | 0.64%	            | father	|               | 
| SAMN08473803	         | 194550	    | F	    | 43.32	        | 9915	    | Brahman	            | BR 	     | 12	        | 0.64%	            | mother	|               | 
| SAMN12153487	         | 341497	    | F	    | 17.92	        | 331036    | YakScottishHighlander | F1X	     | 13	        | 0.48%	            | offspring	| 15            | 
| SAMN12153485	         | 204543	    | M	    | 34.69	        | 9913	    | ScottishHighlander	| HI	     | 13	        | 0.48%	            | father	|               | 
| SAMN12153486	         | 204544	    | F	    | 10.66	        | 30521	    | Yak	                | YK	     | 13	        | 0.48%	            | mother	|               | 
| SAMN16780309	         | 341713	    | M	    | 14.46	        | 297284	| BisonSimmental	    | F1X	     | 14	        | 1.10%	            | offspring	| 16            | 
| SAMN16823422	         | 341714	    | M	    | 27.44	        | 9901	    | Bison	                | BI	     | 14	        | 1.10%	            | father	|               | 
| SAMN16825967	         | 339207	    | F	    | 35.42	        | 9913	    | Simmental	            | SI	     | 14	        | 1.10%	            | mother	|               | 
| SAMN08473802-SYNTHETIC | 9341496	    | M	    | 26.2	        | 30522 	| AngusBrahman          | F1X	     | 15	        | 0.68%	            | offspring	| 17            | 
| SAMN08473804	         | 194551	    | M	    | 36.99	        | 9913	    | Angus     	        | AA	     | 15	        | 0.68%	            | father	|               | 
| SAMN08473803	         | 194550	    | F	    | 43.32	        | 9915	    | Brahman	            | BR 	     | 15	        | 0.68%	            | mother	|               | 
| SAMN12153487-SYNTHETIC | 9341497	    | F     | 25.79	        | 331036	| YakScottishHighlander | F1X	     | 16	        | 0.87%	            | offspring	| 18            | 
| SAMN12153485	         | 204543	    | M	    | 34.69	        | 9913	    | ScottishHighlander	| HI	     | 16	        | 0.87%	            | father	|               | 
| SAMN12153486	         | 204544	    | F	    | 10.66	        | 30521	    | Yak	                | YK	     | 16	        | 0.87%	            | mother	|               | 
| SAMN16780309-SYNTHETIC | 9341713	    | M	    | 25.85	        | 297284	| BisonSimmental	    | F1X	     | 17	        | 1.42%	            | offspring	| 19            | 
| SAMN16823422	         | 341714	    | M	    | 27.44	        | 9901	    | Bison	                | BI	     | 17	        | 1.42%	            | father	|               | 
| SAMN16825967	         | 339207	    | F	    | 35.42	        | 9913	    | Simmental     	    | SI	     | 17	        | 1.42%	            | mother	|               | 
| SAMN05788479	         | 186	        | M	    | 31.4	        | 9913	    | Angus	                | AA		 | 		        |                   |           | 1             | 
| SAMN13655878	         | 71941    	| M	    | 25.7	        | 9913	    | Shorthorn	            | SH		 | 		        |                   |           | 2             | 
| SAMN10940546	         | 20809	    | M	    | 20.1	        | 9913	    | Charolais	            | CH		 | 		        |                   |           | 3             | 
| SAMN10940570	         | 34095	    | M	    | 20	        | 9913	    | Gelbvieh	            | GB		 | 		        |                   |           | 4             | 
| SAMN03145444	         | 33604	    | F     | 45.5	        | 9913  	| Hereford  	        | HE		 | 		        |                   |           | 5             | 
| SAMN10940696	         | 185699   	| M	    | 24.1	        | 9913	    | Jersey	            | JE		 | 	            |                   |           | 6             | 
| SAMN10940544	         | 18336	    | M     | 20.7	        | 9913	    | Limousin	            | LM		 | 		        |                   |           | 7             | 
| SAMN05788560	         | 87957	    | M	    | 22.2	        | 9913	    | MaineAnjou	        | MA		 | 		        |                   |           | 8             | 
| SAMN13655862	         | 51124	    | M	    | 24.9	        | 9913	    | Salers	            | SL		 | 		        |                   |           | 9             | 
| SAMN05788545	         | 71657	    | M	    | 24.5  	    | 9913	    | Simmental	            | SI		 | 		        |                   |           | 10            | 
| SAMEA4780288	         | 196818	    | M	    | 52.8	        | 9913  	| Holstein	            | HO		 | 		        |                   |           | 11            | 
| SAMN05216092	         | 194426	    | M	    | 13.5	        | 9913	    | Chianina	            | CI		 | 		        |                   |           | 12            | 
| SAMEA6272116	         | 204654       | M     | 60            | 9913      | BrownSwiss            | BS         |              |                   |           | 13            | 