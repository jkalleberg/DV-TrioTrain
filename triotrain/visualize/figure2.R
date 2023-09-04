#!/usr/bin/R

# helper functions
setwd("./deep-variant/results/v1.4.0/R_visuals")
source("helpers.R")
define_logger()
wrapper("start")

load_libraries(c(
    "rjson",
    "here",
    "tidyverse",
    "ggplot2",
    "reshape2",
    "fplot",
    "RColorBrewer"
))

n_trios <- 15

add_labels <- function(phase, itr, train_genome) {
    labeled_list <- list()
    labeled_list["TrainingPhase"] <- phase
    labeled_list["TrioNum"] <- itr
    labeled_list["TrainingGenome"] <- train_genome
    return(labeled_list)
}

itr <- 0

# --- Abreviated Data Labels on X Axis | ALL PHASES --- #
metrics_data_frame <- data.frame()
parents <- c("Father", "Mother")

# read in all raw data files
for (i in seq(from = 1, to = n_trios, by = 1)) {
    phase <- check_phase(i)

    for (p in seq_along(parents)) {
        cat(sprintf("=== TRIO%s | %s | ITR: %d ====\n", i, parents[p], itr))
        data_labels <- add_labels(phase, i, parents[p])
        json_data <- fromJSON(file = here(
            "data",
            sprintf("trio%s.%s.best_checkpoint.metrics", i, parents[p])
        ))
        data_list <- as.list(json_data)
        values <- as.numeric(data_list)
        labeled_data <- as.data.frame(
            c(data_labels, values),
            col.names = c(names(data_labels), names(data_list))
        )

        if (itr == 0) {
            metrics_data_frame <- labeled_data
        } else {
            metrics_data_frame <- rbind(
                metrics_data_frame,
                labeled_data
            )
        }
        itr <- itr + 1
    }
}

# caclulate overall F1.score for each variant type
df <- metrics_data_frame %>% mutate(
    F1.SNPs = 2 * (
        (`Precision.SNPs` * `Recall.SNPs`) /
            (`Precision.SNPs` + `Recall.SNPs`)),
    F1.Indels = 2 * (
        (`Precision.Indels` * `Recall.Indels`) /
            (`Precision.Indels` + `Recall.Indels`))
)

# only look at F1-score
df2 <- df %>% dplyr::select(
    contains(
        c("train", "trio", "F1"),
        ignore.case = TRUE
    )
)

# calculate an average since F1-All = F1.Het
# create a unique label for each iteration
df3 <- df2 %>% mutate(
    F1.Avg = (
        `F1.Het` + `F1.HomRef` + `F1.HomVar` + `F1.SNPs` + `F1.Indels`) / 5,
    label = sprintf(
        "Phase %d:%s - T%s",
        df2$TrainingPhase,
        substr(df2$TrainingGenome, 1, 1),
        df2$TrioNum
    )
)

# drop unecessary columns that interfer with melt()
df4 <- subset(df3, select = -c(
    TrainingPhase, TrainingGenome, TrioNum, `F1.All`
))

# shape data for easy ggplot visuals
df5 <- reshape2::melt(df4, id.vars = "label")


# split label up for grouping
df6 <- df5 %>% separate(
    label,
    into = c("Phase", "RunName"), sep = ":"
)

# use entire train genome name to avoid confusing Mother/Father with Male/Female
df7 <- df6 %>% mutate(
    TrainOrder = as.numeric(str_extract(RunName, "\\d+")),
    TrainingGenome = case_when(
        grepl("F", RunName) ~ "Father",
        grepl("M", RunName) ~ "Mother"
    )
)

# ensure that Train Order repeats for each metric
iteration_num <- rep(
    as.numeric(rownames(df2)),
    nrow(df7) / length(rownames(df2))
)

# create the x-axis labels
df8 <- df7 %>% mutate(
    ModelName = sprintf(
        "T%s - %s",
        df7$TrainOrder,
        iteration_num
    )
)

# enable grouping by phase
df8$Phase <- factor(
    df8$Phase,
    levels = unique(df8$Phase),
    ordered = TRUE
)

# enable grouping by model
df8$ModelName <- factor(
    df8$ModelName,
    levels = unique(df8$ModelName[order(df8$TrainOrder)])
)

# display.brewer.pal(n = 9, name = "Greys")
# brewer.pal(n = 9, name = "Greys")

# make the supplement plot
# p <- ggplot(
#     df8,
#     aes(
#         ModelName,
#         value,
#         color = variable,
#         shape = TrainingGenome,
#         linetype = variable
#         )) + scale_shape_manual(values = c(15, 16)) +
#         geom_point(size = 2) +
#         geom_line(aes(group = variable)) +
#         geom_point(color = "white", size = 1) +
#         theme_classic() + # white background
#         scale_color_manual(
#             name = element_blank(),
#             breaks = c(
#                 "F1.HomRef",
#                 "F1.Het",
#                 "F1.HomVar",
#                 "F1.SNPs",
#                 "F1.Indels",
#                 "F1.Avg"
#             ),
#             labels = c(
#                 "HomRef",
#                 "Het",
#                 "HomVar",
#                 "SNPs",
#                 "INDELs",
#                 "Average"
#             ), # remove F1 from labels
#             values = c(
#                 # "#D9D9D9",
#                 "#BDBDBD",
#                 "#969696",
#                 "#737373",
#                 "#252525",
#                 "#737373",
#                 "#000000"
#             ), # increase contrast between colors
#         ) +
#         scale_linetype_manual(
#             name = element_blank(),
#             breaks = c(
#                 "F1.HomRef",
#                 "F1.Het",
#                 "F1.HomVar",
#                 "F1.SNPs",
#                 "F1.Indels",
#                 "F1.Avg"
#             ),
#             labels = c(
#                 "HomRef",
#                 "Het",
#                 "HomVar",
#                 "SNPs",
#                 "INDELs",
#                 "Average"
#             ), # remove F1 from labels
#             values = c(
#             "dashed",
#             "dashed",
#             "dashed",
#             "solid",
#             "solid",
#             "dashed"),
#         ) +
#         xlab("Trio - Training Iteration") + # update y-axis title
#         ylab("F1-Score") + # update y-axis title
#         theme(
#             axis.title = element_text(
#                 face = "bold"), # bold axis titles
#             axis.text.x = element_text(
#                 angle = 45,
#                 hjust = 1), # turn the x-axis test on a 45 deg angle
#             panel.grid.major.x = element_line(
#                 color = "#d4d2d2",
#                 linetype = "dotted"
#                 ), # add a faint dotted grey y-axis major lines
#             legend.title = element_blank(), # remove legend title
#             legend.position = "bottom", # move legend to bottom left
#             legend.box.just = "left",
#             legend.box = "horizontal",
#             legend.margin = margin(
#                 t = -7), # shrink space between x-axis and legend
#             legend.text = element_text(
#                 margin = margin(
#                     r = .5, unit = "mm"
#                     )), # increase space between legend items
#             legend.key.width = unit(
#                 12, "mm"), # increase the length of line displayed in legend
#             strip.text = element_text(
#                 colour = "white",
#                 face = "bold"
#             ) # use white text for facets
#         ) +
#         facet_grid(
#             cols = vars(Phase), # create boundaries for each phase
#             scales = "free", # shrink excess white space
#             space = "free") +
#         guides(
#                 linetype = guide_legend(
#                     ncol = 6,
#                     order = 1, # display linetype before color
#                     label.hjust = 0.5
#                 ),
#                 shape = guide_legend(
#                     ncol = 3,
#                     order = 2, # display color before shape
#                     label.hjust = 0.5),
#                 col = guide_legend(
#                     ncol = 6, # display all colors in one line
#                     order = 1,
#                     label.hjust = 0.5
#                 )
#             )

# add a column for alpha values
# df8$alpha <- grepl("F1.Avg", df8$variable)
# alpha_vals <- ifelse(df8$alpha, 0.9, 0.15)

p <- ggplot(
    df8,
    aes(
        ModelName,
        value)
) +
    geom_line(aes(
        group = variable,
        linetype = variable),
        color = "#383838") +
    scale_linetype_manual(
        name = element_blank(),
        breaks = c(
            "F1.HomRef",
            "F1.Het",
            "F1.HomVar",
            "F1.SNPs",
            "F1.Indels",
            "F1.Avg"
        ),
        labels = c(
            "HomRef",
            "Het",
            "HomVar",
            "SNPs",
            "INDELs",
            "Average"
        ), # remove F1 from labels
        values = c(
            "solid",
            "solid",
            "solid",
            "solid",
            "solid",
            "dashed"
        ),
    ) + # only average will have a dashed line
    geom_point(
        aes(
            shape = variable,
            alpha = variable,
            fill = TrainingGenome
        ),
        size = 2
    ) +
    scale_alpha_manual(
        name = element_blank(),
        breaks = c(
            "F1.HomRef",
            "F1.Het",
            "F1.HomVar",
            "F1.SNPs",
            "F1.Indels",
            "F1.Avg"
        ),
        labels = c(
            "HomRef",
            "Het",
            "HomVar",
            "SNPs",
            "INDELs",
            "Average"
        ), # remove F1 from labels
        values = c(
            0.6,
            0.6,
            0.6,
            0.6,
            0.6,
            0.95
        )
    ) + # only average will not be transparent
    scale_shape_manual(
            name = element_blank(),
            breaks = c(
                "F1.HomRef",
                "F1.Het",
                "F1.HomVar",
                "F1.SNPs",
                "F1.Indels",
                "F1.Avg"
            ),
            labels = c(
                "HomRef",
                "Het",
                "HomVar",
                "SNPs",
                "INDELs",
                "Average"
            ), # remove F1 from labels
            values = c(
                23,
                24,
                25,
                21,
                22,
                4
            )
    ) + # only average will not have an open shape
    scale_fill_manual(
        name = element_blank(),
        values = c(
            "Mother" = "#61696b",
            "Father" = "#d41c43"
        ),
        guide = "none"
    ) + # manually set colors to differ from phase colors
    theme_classic() + # white background
    xlab("Trio - Training Iteration") + # update y-axis title
    ylab("F1-Score") + # update y-axis title
    theme(
        axis.title = element_text(
            face = "bold"
        ), # bold axis titles
        axis.text.x = element_text(
            angle = 45,
            hjust = 1
        ), # turn the x-axis test on a 45 deg angle
        panel.grid.major.x = element_line(
            color = "#d4d2d2",
            linetype = "dotted"
        ), # add a faint dotted grey y-axis major lines
        legend.title = element_blank(), # remove legend title
        legend.position = "bottom", # move legend to bottom left
        legend.box.just = "left",
        legend.box = "horizontal",
        legend.margin = margin(
            t = -7
        ), # shrink space between x-axis and legend
        legend.text = element_text(
            margin = margin(
                r = 3, l = -2, unit = "mm"
            )
        ), # increase space between legend items, and
        # move the text closer to the item
        legend.key.width = unit(
            12, "mm"
        ), # increase the length of line displayed in legend
        strip.text = element_text(
            colour = "white",
            face = "bold"
        ) # use white text for facets
    ) +
    facet_grid(
        cols = vars(Phase), # create boundaries for each phase
        scales = "free", # shrink excess white space
        space = "free"
    ) +
    guides(
        alpha = FALSE, # suppress the alpha scale from legend
        linetype = guide_legend(
            ncol = 6,
            order = 1, # display linetype before color
            label.hjust = 0.5
        ),
        shape = guide_legend(
            ncol = 6,
            order = 1, # display color before shape
            label.hjust = 0.5,
            override.aes = list(fill = c(
                "white"
            ))
        ),
        fill = guide_legend(
            label.hjust = 0.5,
            override.aes = list(color = c(
            "#d41c43",
            "#61696b"
        ))) # over-ride to have colors appear correctly in legend
    )

p

# add phase colors to facet labels
g1 <- ggplot_gtable(ggplot_build(p))
striprt <- which(
    grepl("strip-r", g1$layout$name) | grepl("strip-t", g1$layout$name)
)
fills <- c(c(
    "#d95f02",
    "#7570b3",
    "#e7298b",
    "#67a61e",
    "#e6a902"
))

k <- 1
for (i in striprt) {
    j <- which(grepl("rect", g1$grobs[[i]]$grobs[[1]]$childrenOrder))
    g1$grobs[[i]]$grobs[[1]]$children[[j]]$gp$fill <- fills[k]
    k <- k + 1
}
grid::grid.draw(g1)

# save the image with the correct font size and aspect ratio
pdf_fit(
    "23.05.05.Supp_TrainingF1-Score.all_phases.pdf",
    pt = 10, # font size
    sideways = TRUE, # landscape orientation
    w2h = 2.125, # aspect ratio 170mm/80mm
)
grid::grid.draw(g1)
invisible(dev.off())


## REMOVE PHASE 5 FOR MAIN BODY OF MANUSCRIPT ---------------##
# remove Phase 5 only
df9 <- dplyr::filter(df8, !grepl("Phase 5", Phase))

# make the main plot
# p2 <- ggplot(
#     df9,
#     aes(
#         ModelName,
#         value,
#         color = variable,
#         shape = TrainingGenome,
#         linetype = variable
#         )) + scale_shape_manual(values = c(15, 16)) +
#         geom_point(size = 2) +
#         geom_line(aes(group = variable)) +
#         geom_point(color = "white", size = 1) +
#         theme_classic() + # white background
#         scale_color_manual(
#             name = element_blank(),
#             breaks = c(
#                 "F1.HomRef",
#                 "F1.Het",
#                 "F1.HomVar",
#                 "F1.SNPs",
#                 "F1.Indels",
#                 "F1.Avg"
#             ),
#             labels = c(
#                 "HomRef",
#                 "Het",
#                 "HomVar",
#                 "SNPs",
#                 "INDELs",
#                 "Average"
#             ), # remove F1 from labels
#             values = c(
#                 # "#D9D9D9",
#                 "#BDBDBD",
#                 "#969696",
#                 "#737373",
#                 "#252525",
#                 "#737373",
#                 "#000000"
#             ), # increase contrast between colors
#         ) +
#         scale_linetype_manual(
#             name = element_blank(),
#             breaks = c(
#                 "F1.HomRef",
#                 "F1.Het",
#                 "F1.HomVar",
#                 "F1.SNPs",
#                 "F1.Indels",
#                 "F1.Avg"
#             ),
#             labels = c(
#                 "HomRef",
#                 "Het",
#                 "HomVar",
#                 "SNPs",
#                 "INDELs",
#                 "Average"
#             ), # remove F1 from labels
#             values = c(
#             "dashed",
#             "dashed",
#             "dashed",
#             "solid",
#             "solid",
#             "dashed"),
#         ) +
#         xlab("Trio - Training Iteration") + # update y-axis title
#         ylab("F1-Score") + # update y-axis title
#         theme(
#             axis.title = element_text(
#                 face = "bold"), # bold axis titles
#             axis.text.x = element_text(
#                 angle = 45,
#                 hjust = 1), # turn the x-axis test on a 45 deg angle
#             panel.grid.major.x = element_line(
#                 color = "#d4d2d2",
#                 linetype = "dotted"
#                 ), # add a faint dotted grey y-axis major lines
#             legend.title = element_blank(), # remove legend title
#             legend.position = "bottom", # move legend to bottom left
#             legend.box.just = "left",
#             legend.box = "horizontal",
#             legend.margin = margin(
#                 t = -7), # shrink space between x-axis and legend
#             legend.text = element_text(
#                 margin = margin(
#                     r = .5, unit = "mm"
#                     )), # increase space between legend items
#             legend.key.width = unit(
#                 12, "mm"), # increase the length of line displayed in legend
#             strip.text = element_text(
#                 colour = "white",
#                 face = "bold"
#             ) # use white text for facets
#         ) +
#         facet_grid(
#             cols = vars(Phase), # create boundaries for each phase
#             scales = "free", # shrink excess white space
#             space = "free") +
#         guides(
#                 linetype = guide_legend(
#                     ncol = 6,
#                     order = 1, # display linetype before color
#                     label.hjust = 0.5
#                 ),
#                 shape = guide_legend(
#                     ncol = 3,
#                     order = 2, # display color before shape
#                     label.hjust = 0.5),
#                 col = guide_legend(
#                     ncol = 6, # display all colors in one line
#                     order = 1,
#                     label.hjust = 0.5
#                 )
#             )

p2 <- ggplot(
    df9,
    aes(
        ModelName,
        value
    )
) +
    geom_line(
        aes(
            group = variable,
            linetype = variable
        ),
        color = "#383838"
    ) +
    scale_linetype_manual(
        name = element_blank(),
        breaks = c(
            "F1.HomRef",
            "F1.Het",
            "F1.HomVar",
            "F1.SNPs",
            "F1.Indels",
            "F1.Avg"
        ),
        labels = c(
            "HomRef",
            "Het",
            "HomVar",
            "SNPs",
            "INDELs",
            "Average"
        ), # remove F1 from labels
        values = c(
            "solid",
            "solid",
            "solid",
            "solid",
            "solid",
            "dashed"
        ),
    ) + # only average will have a dashed line
    geom_point(
        aes(
            shape = variable,
            alpha = variable,
            fill = TrainingGenome
        ),
        size = 2
    ) +
    scale_alpha_manual(
        name = element_blank(),
        breaks = c(
            "F1.HomRef",
            "F1.Het",
            "F1.HomVar",
            "F1.SNPs",
            "F1.Indels",
            "F1.Avg"
        ),
        labels = c(
            "HomRef",
            "Het",
            "HomVar",
            "SNPs",
            "INDELs",
            "Average"
        ), # remove F1 from labels
        values = c(
            0.6,
            0.6,
            0.6,
            0.6,
            0.6,
            0.95
        )
    ) + # only average will not be transparent
    scale_shape_manual(
        name = element_blank(),
        breaks = c(
            "F1.HomRef",
            "F1.Het",
            "F1.HomVar",
            "F1.SNPs",
            "F1.Indels",
            "F1.Avg"
        ),
        labels = c(
            "HomRef",
            "Het",
            "HomVar",
            "SNPs",
            "INDELs",
            "Average"
        ), # remove F1 from labels
        values = c(
            23,
            24,
            25,
            21,
            22,
            4
        )
    ) + # only average will not have an open shape
    scale_fill_manual(
        name = element_blank(),
        values = c(
            "Mother" = "#61696b",
            "Father" = "#d41c43"
        ),
        guide = "none"
    ) + # manually set colors to differ from phase colors
    theme_classic() + # white background
    xlab("Trio - Training Iteration") + # update y-axis title
    ylab("F1-Score") + # update y-axis title
    theme(
        axis.title = element_text(
            face = "bold"
        ), # bold axis titles
        axis.text.x = element_text(
            angle = 45,
            hjust = 1
        ), # turn the x-axis test on a 45 deg angle
        panel.grid.major.x = element_line(
            color = "#d4d2d2",
            linetype = "dotted"
        ), # add a faint dotted grey y-axis major lines
        legend.title = element_blank(), # remove legend title
        legend.position = "bottom", # move legend to bottom left
        legend.box.just = "left",
        legend.box = "horizontal",
        legend.margin = margin(
            t = -7
        ), # shrink space between x-axis and legend
        legend.text = element_text(
            margin = margin(
                r = 3, l = -2, unit = "mm"
            )
        ), # increase space between legend items, and
        # move the text closer to the item
        legend.key.width = unit(
            12, "mm"
        ), # increase the length of line displayed in legend
        strip.text = element_text(
            colour = "white",
            face = "bold"
        ) # use white text for facets
    ) +
    facet_grid(
        cols = vars(Phase), # create boundaries for each phase
        scales = "free", # shrink excess white space
        space = "free"
    ) +
    guides(
        alpha = FALSE, # suppress the alpha scale from legend
        linetype = guide_legend(
            ncol = 6,
            order = 1, # display linetype before color
            label.hjust = 0.5
        ),
        shape = guide_legend(
            ncol = 6,
            order = 1, # display color before shape
            label.hjust = 0.5,
            override.aes = list(fill = c(
                "white"
            ))
        ),
        fill = guide_legend(
            label.hjust = 0.5,
            override.aes = list(color = c(
                "#d41c43",
                "#61696b"
            ))
        ) # over-ride to have colors appear correctly in legend
    )

p2

# add phase colors to facet labels
g <- ggplot_gtable(ggplot_build(p2))
striprt <- which(
    grepl("strip-r", g$layout$name) | grepl("strip-t", g$layout$name)
)
fills <- c(c(
    "#D95F02",
    "#7570B3",
    "#E7298A",
    "#66A61E"
))

k <- 1
for (i in striprt) {
    j <- which(grepl("rect", g$grobs[[i]]$grobs[[1]]$childrenOrder))
    g$grobs[[i]]$grobs[[1]]$children[[j]]$gp$fill <- fills[k]
    k <- k + 1
}
grid::grid.draw(g)

# save the image with the correct font size and aspect ratio
pdf_fit(
    "23.05.05.Fig2_TrainingF1-Score.phases1-4.pdf",
    pt = 10, # font size
    sideways = TRUE, # landscape orientation
    w2h = 2.125, # aspect ratio 170mm/80mm
)
grid::grid.draw(g) # ggplot variable
invisible(dev.off())

wrapper("end")
