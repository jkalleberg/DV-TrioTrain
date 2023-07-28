#!/usr/bin/R

# helper functions
setwd("./deep-variant/results/v1.4.0/R_visuals")
source("helpers.R")
source("coord_cartesian_panels.R")
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

# Cow Samples + Cow Models
cow_trio_train_results <- read.csv(
    "./data/230323_TrioTrain_AllRuns.total.metrics.csv"
)

# Cow Samples + Default Model
cow_default_results <- read.csv(
    "./data/DV1.4_default_human.AllTests.total.metrics.csv"
)

# Cow Samples + WGS.AF Model
cow_af_results <- read.csv(
    "./data/DV1.4_WGS.AF_human.AllTests.total.metrics.csv"
)

# Cow Samples + DeepTrio Model
cow_dt_results <- read.csv(
    "./data/230324_DT.AllTests.total.metrics.csv"
)

# merge all results files
df <- plyr::rbind.fill(
    cow_dt_results,
    cow_af_results,
    cow_default_results,
    cow_trio_train_results
)

# replace sep for string splitting
df$test_name <- str_replace(df$test_name, "_default_human", "-default-human")
df$test_name <- str_replace(df$test_name, "_WGS.AF_human", "-WGS.AF-human")

# --- Long Data Labels on Y-axis | ALL PHASES --- #
# select F1-score metric only
df1 <- df %>% filter(str_detect(test_name, "F1-"))

# re-shape data for easy ggplot visuals
df2 <- reshape2::melt(df1, id.vars = "test_name")

# update column names
colnames(df2)[1] <- "Category"
colnames(df2)[2] <- "TestName"

# split up model name strings
df3 <- df2 %>% separate(Category, c("RunName", "Type", "Metric"), "_")

# add train order for easy sorting
df4 <- df3 %>% mutate(
    TrainOrder = case_when(
        grepl("human", RunName) ~ 0,
        !grepl("human", RunName) ~ readr::parse_number(
            as.character(RunName)
        )
    )
)

# ensure no confusion between Mother/Father and Male/Female
# re-work model name so Trio# lines up against y-axis
df5 <- df4 %>% mutate(
    TrainingGenome = case_when(
        grepl("human", RunName) ~ "None",
        grepl("-F", RunName) ~ "Father",
        grepl("-M", RunName) ~ "Mother"
    ),
    ModelName = case_when(
        grepl("human", RunName) ~ RunName,
        !grepl("human", RunName) ~ sprintf(
            "%s - Trio%s", TrainingGenome, TrainOrder
        )
    )
)

# shorten model names
df5$RunName <- str_replace(df5$RunName, "-human", "")
df5$ModelName <- str_replace(df5$ModelName, "-human", "")

# remove any missing values that occur due to DT not being run on all tests
clean_df <- na.omit(df5)
clean_df$value <- as.numeric(clean_df$value)

# add a phase name for coloring
df6 <- clean_df %>% mutate(
    Phase = mapply(function(x) check_phase(x), TrainOrder)
)

# create factor variables
df6$ModelName <- factor(
    df6$ModelName,
    levels = rev(unique(df6$ModelName)),
    ordered = TRUE,
)

df6$Type <- factor(
    df6$Type,
    levels = c("SNPs", "INDELs", "Total"),
)

df6$Phase <- factor(
    df6$Phase,
    levels = unique(df6$Phase),
    ordered = TRUE
)

# Now filter out the Type that we don't want
df6 <- filter(df6, Type != "Total")

# determine the outlier whisker value for Father 12 - SNPs
head(df6 %>%
    group_by(ModelName, Type) %>%
    summarize(min_F1Score = min(value)), n = 16)

# make the supplement plot
p <- ggplot(
    data = df6,
    mapping = aes(
        x = value,
        y = ModelName, # flip the X and Y so that long labels can be read
        fill = Phase,
    )) +
    stat_boxplot(geom = "errorbar", width = 0.6) +
    geom_boxplot(width = 0.6) +
    theme_classic() + # white background
    facet_grid(
        . ~ Type, # create boundaries for variant type
        scales = "free" # shrink excess white space
        ) +
    coord_cartesian_panels(
        panel_limits <- tibble::tribble(
        ~Type, ~xmin, ~xmax,
        "SNPs", 0.9, 1,
        "INDELs", 0.8, 1)) + # vary the axis limits
    xlab("F1-Score") + # update x-axis title
    ylab("Model") + # update y-axis title
    scale_fill_brewer(
        palette = "Dark2",
        breaks = c(
            0,
            3,
            1,
            4,
            2,
            5
        ),
        labels = c(
            "Exising Models",
            "Phase 3",
            "Phase 1",
            "Phase 4",
            "Phase 2",
            "Phase 5"
        )# clarify phase
    ) + # increase contrast between colors
    theme(
        axis.title = element_text(
            face = "bold"
        ), # bold axis titles
        axis.text.x = element_text(
            angle = 45,
            hjust = 1
        ), # turn the x-axis test on a 45 deg angle
        axis.title.x = element_text(
            margin = unit(c(3, 0, 1, 0), "mm")
            ), # increase the spacing between x-axis and axis title
        panel.grid.major.y = element_line(
            color = "#d4d2d2",
            linetype = "dotted"
        ), # add a faint dotted grey y-axis major lines
        panel.spacing.x = unit(
            6, "mm"
        ), # change horizontal spacing between facets
        legend.title = element_blank(), # remove legend title
        legend.box = "horizontal",
        legend.margin = margin(
            t = -3, unit = "mm"
        ), # shrink space between x-axis and legend
        legend.text = element_text(
            margin = margin(
                r = 2, unit = "mm"
            ) # increase space between legend items
        ),
        legend.position = "bottom", # move legend to bottom left
        strip.text = element_text(
            colour = "white",
            face = "bold"
        ) # use white text for facets
    )  +
    guides(fill = guide_legend(
        ncol = 3, # display all colors in one line
        label.hjust = 0.5
    ))
p

# add phase colors to facet labels
g <- ggplot_gtable(ggplot_build(p))
striprt <- which(
    grepl("strip-r", g$layout$name) | grepl("strip-t", g$layout$name)
)

fills <- c(
    "#252525",
    "#737373"
)

k <- 1
for (i in striprt) {
    j <- which(grepl("rect", g$grobs[[i]]$grobs[[1]]$childrenOrder))
    g$grobs[[i]]$grobs[[1]]$children[[j]]$gp$fill <- fills[k]
    k <- k + 1
}
grid::grid.draw(g)

# save the image with the correct font size and aspect ratio
pdf_fit(
    "Supp_TrioTrain.TestingF1-Score.all_phases.pdf",
    pt = 10, # font size
    h2w = 1.76, # aspect ratio 150mm/85mm
)
grid::grid.draw(g)
invisible(dev.off())


## REMOVE PHASE 5 FOR MAIN BODY OF MANUSCRIPT ---------------##
# remove Phase 5 only
df7 <- dplyr::filter(df6, !grepl(5, Phase))

# make the main plot
p2 <- ggplot(
    data = df7,
    mapping = aes(
        x = value,
        y = ModelName, # flip the X and Y so that long labels can be read
        fill = Phase,
    )
) +
    stat_boxplot(geom = "errorbar", width = 0.6) +
    geom_boxplot(width = 0.6) +
    theme_classic() + # white background
    facet_grid(
        . ~ Type, # create boundaries for variant type
        scales = "free" # shrink excess white space
    ) +
    coord_cartesian_panels(
        panel_limits <- tibble::tribble(
            ~Type, ~xmin, ~xmax,
            "SNPs", 0.9, 1,
            "INDELs", 0.8, 1
        )
    ) + # vary the axis limits
    xlab("F1-Score") + # update x-axis title
    ylab("Model") + # update y-axis title
    scale_fill_brewer(
        palette = "Dark2",
        breaks = c(
            0,
            1,
            2,
            3,
            4,
            5
        ),
        labels = c(
            "Exising Models",
            "Phase 1",
            "Phase 2",
            "Phase 3",
            "Phase 4",
            "Phase 5"
        ) # clarify phase
    ) + # increase contrast between colors
    theme(
        axis.title = element_text(
            face = "bold"
        ), # bold axis titles
        axis.text.x = element_text(
            angle = 45,
            hjust = 1
        ), # turn the x-axis test on a 45 deg angle
        axis.title.x = element_text(
            margin = unit(c(3, 0, 1, 0), "mm")
        ), # increase the spacing between x-axis and axis title
        panel.grid.major.y = element_line(
            color = "#d4d2d2",
            linetype = "dotted"
        ), # add a faint dotted grey y-axis major lines
        panel.spacing.x = unit(
            6, "mm"
        ), # change horizontal spacing between facets
        legend.title = element_blank(), # remove legend title
        legend.box = "horizontal",
        legend.margin = margin(
            t = -3, unit = "mm"
        ), # shrink space between x-axis and legend
        legend.text = element_text(
            margin = margin(
                r = 2, unit = "mm"
            ) # increase space between legend items
        ),
        legend.position = "bottom", # move legend to bottom left
        strip.text = element_text(
            colour = "white",
            face = "bold"
        ) # use white text for facets
    ) +
    guides(fill = guide_legend(
        ncol = 6, # display all colors in one line
        label.hjust = 0.5
    ))
p2

# add phase colors to facet labels
g2 <- ggplot_gtable(ggplot_build(p2))
striprt <- which(
    grepl("strip-r", g2$layout$name) | grepl("strip-t", g2$layout$name)
)
fills <- c(
    "#252525",
    "#737373"
)

k <- 1
for (i in striprt) {
    j <- which(grepl("rect", g2$grobs[[i]]$grobs[[1]]$childrenOrder))
    g2$grobs[[i]]$grobs[[1]]$children[[j]]$gp$fill <- fills[k]
    k <- k + 1
}
grid::grid.draw(g2)

# save the image with the correct font size and aspect ratio
pdf_fit(
    "Fig3_TrioTrain.TestingF1-Score.phases1-4.pdf",
    pt = 10, # font size
    h2w = 1.76, # aspect ratio 150mm/85mm
)
grid::grid.draw(g2)
invisible(dev.off())

wrapper("end")
