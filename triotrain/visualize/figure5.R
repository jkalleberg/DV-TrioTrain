# helper functions
setwd("./R_visuals")
source("helpers.R")
define_logger()
wrapper("start")
load_libraries(c(
    "tidyverse",
    "stringr",
    "ggplot2",
    "reshape2",
    "dplyr",
    "fplot"
))

# Human Samples + All Models
mendelian_results <- read.csv(
    # "./data/230213_mendelian.csv"
    "./data/230518_mendelian.csv"
)

# remove results from the Mosquito model
no_skeeters <- mendelian_results[!grepl("Mosquito", mendelian_results$info), ]

# determine how many models were tested per sample
sorted_data <- no_skeeters[with(no_skeeters, order(sampleID, sort)), ]
sorted_data %>% count(info)

# only include samples with all 9 models
# aka exclude the MIE runs from non-F1 training trios
filtered_data <- sorted_data %>% group_by(info) %>% filter(n() >= 9)

# confirm which samples were removed
filtered_data %>% count(info)

# extract Trio# from label
df1 <- as.data.frame(filtered_data) %>% mutate(
    order = as.numeric(str_extract(label, "\\d+"))
)

# shorten model names
# keep format consistent with previous figures
df1$variant_caller <- str_replace(
    df1$variant_caller, "DV1.4_WGS.AF_cattle", "Phase "
)
df1$variant_caller <- str_replace(
    df1$variant_caller, "DT1.4_default_human", "DT1.4-default"
)
df1$variant_caller <- str_replace(
    df1$variant_caller, "DV1.4_default_human", "DV1.4-default"
)
df1$variant_caller <- str_replace(
    df1$variant_caller, "DV1.4_WGS.AF_human", "DV1.4-WGS.AF"
)

df1$variant_caller <- str_replace(
    df1$variant_caller, "GATK4_PostVQSR_UMAGv1", "UMAGv"
)

# turn the string % into numeric values
df2 <- df1 %>% mutate(
    MendelianErrorPct = parse_number(mendelian_error_rate) / 100
)

# remove 0% mendelian error rate
drop_zeros <- filter(df2, MendelianErrorPct > 0)

# remove the "GATK" training vcfs
drop_training <- drop_zeros[!grepl("train", drop_zeros$filter), ]

drop_training$variant_caller <- factor(
    drop_training$variant_caller,
    levels = c(
        "GIAB_v.4.2.1",
        "DT1.4-default",
        "DV1.4-WGS.AF",
        "DV1.4-default",
        "Phase 1",
        "Phase 2",
        "Phase 3",
        "Phase 4",
        "Phase 5"
    ),
    ordered = TRUE
)

# Abbreviate breeds to match Table 1
drop_training$info <- str_replace(
    drop_training$info, "AngusBrahmanF1", "AA/BR"
)
drop_training$info <- str_replace(
    drop_training$info, "YakHighlanderF1", "YK/HI"
)
drop_training$info <- str_replace(
    drop_training$info, "BisonSimmentalF1", "BI/SI"
)

# Use a more generic descriptor since using F1-hybrids only
drop_training$info <- str_replace(
    drop_training$info, "Cow", "Bovine"
)

# Abbreviate Synthetic
drop_training$info <- str_replace(
    drop_training$info, "Synthetic", "SYN-"
)
drop_training$info <- str_replace(
    drop_training$info, "Syntethic", "SYN-"
)

# change delimiter
drop_training$info <- str_replace(
    drop_training$info, "_", " "
)

# set order for samples
drop_training$info <- factor(
    drop_training$info,
    levels = c(
        "Human Chinese",
        "Human Ashkenazi",
        "Bovine AA/BR",
        "Bovine YK/HI",
        "Bovine BI/SI",
        "Bovine SYN-AA/BR",
        "Bovine SYN-YK/HI",
        "Bovine SYN-BI/SI"
    )
)

# re-order data so trios plot correctly
re_sorted_data <- drop_training[with(
    drop_training, order(order, sampleID, variant_caller)
), ]

# make the supplement plot
p <- ggplot(re_sorted_data, aes(
    x = info,
    y = MendelianErrorPct
)) +
    geom_col(aes(fill = variant_caller,
        group = variant_caller),
        # size = 0.5,
        width = 0.8,
        position = position_dodge(0.80),
        color = "black"
        ) +
    theme_classic() + # white background
    scale_y_continuous(
        expand = c(0, 0),
        limits = c(0, 0.0125),
        labels = scales::percent
    ) + # remove extra space between axis and bars, display the Y axis as a %
    scale_x_discrete(
        labels = function(x) str_wrap(x, width = 6)
        ) + # wrap the x-axis labels
    xlab("Trio") + # update x-axis title
    ylab("MIE Rate") + # update y-axis title
    scale_fill_manual(values = c(
            "#535353",
            "#1B9E77",
            "#22c998",
            "#28ebb1",
            "#D95F02",
            "#7570B3",
            "#E7298A",
            "#66A61E",
            "#E6AB02"
    )) + # increase contrast between colors
    theme(
        axis.title = element_text(
            face = "bold"
        ), # bold axis titles
        axis.title.x = element_text(
            margin = unit(c(t = 0, r = 0, b = 3, l = 0), "mm")
        ), # increase the spacing between x-axis and axis title
        panel.grid.major.y = element_line(
            color = "#d4d2d2",
            linetype = "dotted"
        ), # add a faint dotted grey y-axis major lines 
        legend.title = element_blank(), # remove legend title
        legend.box = "horizontal",
        legend.margin = margin(
            t = -3, unit = "mm"
        ), # shrink space between x-axis and legend
        legend.text = element_text(
            margin = margin(
                r = 5, unit = "mm"
            ) # increase space between legend items
        ),
        legend.position = "bottom" # move legend to bottom left
        ) +
        guides(
            fill = guide_legend(
                ncol = 8, # display all colors in one line
                label.hjust = 0.5
            )
        )

p

# save the image with the correct font size and aspect ratio
pdf_fit(
    "Supp_MIE_rate.all_phases.pdf",
    pt = 10, # font size
    sideways = TRUE, # landscape orientation
    w2h = 2.83, # aspect ratio 170mm/60mm
)
print(p) # ggplot variable
invisible(dev.off())

# for main plot, remove the synthetic samples
no_synth <- re_sorted_data[!grepl("SYN-", re_sorted_data$info), ]
no_synth %>% count(info)

# remove the GIAB/GATK benchmark VCFs, because they skew they are unique
drop_truths <- no_synth[!grepl("GIAB|GATK", no_synth$variant_caller), ]
drop_truths %>% count(info)

# for main plot, remove Phase 5
df3 <- dplyr::filter(drop_truths, !grepl("Phase 5", variant_caller))

# make the main plot
p2 <- ggplot(
    df3,
    aes(
        x = info,
        y = MendelianErrorPct
)) +
    geom_col(
        aes(
            fill = variant_caller,
            group = variant_caller
        ),
        width = 0.8,
        position = position_dodge(0.80),
        color = "black"
    ) +
    theme_classic() + # white background
    scale_y_continuous(
        expand = c(0, 0),
        limits = c(0, 0.0125),
        labels = scales::percent
    ) + # remove extra space between axis and bars, display the Y axis as a %
    scale_x_discrete(
        labels = function(x) str_wrap(x, width = 6)
    ) + # wrap the x-axis labels
    xlab("Trio") + # update x-axis title
    ylab("MIE Rate") + # update y-axis title
    scale_fill_manual(values = c(
        "#1B9E77",
        "#22c998",
        "#28ebb1",
        "#D95F02",
        "#7570B3",
        "#E7298A",
        "#66A61E",
        "#E6AB02"
    )) + # increase contrast between colors
    theme(
        axis.title = element_text(
            face = "bold"
        ), # bold axis titles
        axis.title.x = element_text(
            margin = unit(c(t = 3, r = 0, b = 3, l = 0), "mm")
        ), # increase the spacing between x-axis and axis title
        panel.grid.major.y = element_line(
            color = "#d4d2d2",
            linetype = "dotted"
        ), # add a faint dotted grey y-axis major lines
        legend.title = element_blank(), # remove legend title
        legend.box = "horizontal",
        legend.margin = margin(
            t = -3, unit = "mm"
        ), # shrink space between x-axis and legend
        legend.text = element_text(
            margin = margin(
                r = 5, unit = "mm"
            ) # increase space between legend items
        ),
        legend.position = "bottom" # move legend to bottom left
    ) +
    guides(
        fill = guide_legend(
            ncol = 8, # display all colors in one line
            label.hjust = 0.5
        )
    )

p2

# save the image with the correct font size and aspect ratio
pdf_fit(
    "Fig5_MIE_rate.phases1-4.no-synth.pdf",
    pt = 10, # font size
    sideways = TRUE, # landscape orientation
    w2h = 2.83, # aspect ratio 170mm/60mm
)
print(p2) # ggplot variable
invisible(dev.off())

# make the main plot
p3 <- ggplot(
    no_synth,
    aes(
        x = info,
        y = MendelianErrorPct
    )
) +
    geom_col(
        aes(
            fill = variant_caller,
            group = variant_caller
        ),
        width = 0.8,
        position = position_dodge(0.80),
        color = "black"
    ) +
    theme_classic() + # white background
    scale_y_continuous(
        expand = c(0, 0),
        limits = c(0, 0.0125),
        labels = scales::percent
    ) + # remove extra space between axis and bars, display the Y axis as a %
    scale_x_discrete(
        labels = function(x) str_wrap(x, width = 6)
    ) + # wrap the x-axis labels
    xlab("Trio") + # update x-axis title
    ylab("MIE Rate") + # update y-axis title
    scale_fill_manual(values = c(
        "#1B9E77",
        "#22c998",
        "#28ebb1",
        "#D95F02",
        "#7570B3",
        "#E7298A",
        "#66A61E",
        "#E6AB02"
    )) + # increase contrast between colors
    theme(
        axis.title = element_text(
            face = "bold"
        ), # bold axis titles
        axis.title.x = element_text(
            margin = unit(c(t = 3, r = 0, b = 3, l = 0), "mm")
        ), # increase the spacing between x-axis and axis title
        panel.grid.major.y = element_line(
            color = "#d4d2d2",
            linetype = "dotted"
        ), # add a faint dotted grey y-axis major lines
        legend.title = element_blank(), # remove legend title
        legend.box = "horizontal",
        legend.margin = margin(
            t = -3, unit = "mm"
        ), # shrink space between x-axis and legend
        legend.text = element_text(
            margin = margin(
                r = 5, unit = "mm"
            ) # increase space between legend items
        ),
        legend.position = "bottom" # move legend to bottom left
    ) +
    guides(
        fill = guide_legend(
            ncol = 8, # display all colors in one line
            label.hjust = 0.5
        )
    )

p3

# save the image with the correct font size and aspect ratio
pdf_fit(
    "Fig5_MIE_rate.phases1-5.no-synth.pdf",
    pt = 10, # font size
    sideways = TRUE, # landscape orientation
    w2h = 2.83, # aspect ratio 170mm/60mm
)
print(p3) # ggplot variable
invisible(dev.off())

wrapper("end")

