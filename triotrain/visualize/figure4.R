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

# Human Samples + All Models
GIAB_results <- read.csv(
    "./data/230323_GIAB_AllRuns.total.metrics.csv"
)

GIAB_results$test_name <- str_replace(
    GIAB_results$test_name, "_default_human", "-default-human"
)
GIAB_results$test_name <- str_replace(
    GIAB_results$test_name, "_WGS.AF_", "-WGS.AF-"
)

# --- Long Data Labels on Y-axis | ALL PHASES ---
# select F1-score metric only
df1 <- GIAB_results %>% filter(str_detect(test_name, "F1-"))

# re-shape data for easier ggploting
df2 <- reshape2::melt(df1, id.vars = "test_name")
colnames(df2)[1] <- "Category"
colnames(df2)[2] <- "TestName"

# split out model name for grouping
df3 <- df2 %>% separate(Category, c("ModelName", "Type", "Metric"), "_")

# add model phase
df4 <- df3 %>% mutate(
    Phase = case_when(
        grepl("human", ModelName) ~ 0,
        !grepl("human", ModelName) ~ as.numeric(
            str_extract(ModelName, regex("(\\d+)(?!.*\\d)"))
        )
    )
)

# enabling sting matching and shorten model names
df4$ModelName <- str_replace(
    df4$ModelName, "DV1.4-WGS.AF-cattle", "Phase "
)
df4$ModelName <- str_replace(
    df4$ModelName, "DT1.4-default-human", "DT1.4-default"
)
df4$ModelName <- str_replace(
    df4$ModelName, "DV1.4-default-human", "DV1.4-default"
)
df4$ModelName <- str_replace(
    df4$ModelName, "DV1.4-WGS.AF-human", "DV1.4-WGS.AF"
)

# re-order models run
df5 <- df4 %>%
    arrange(factor(.$ModelName, levels = c(
        "DT1.4-default",
        "DV1.4-WGS.AF",
        "DV1.4-default",
        "Phase 1",
        "Phase 2",
        "Phase 3",
        "Phase 4",
        "Phase 5"
    )))

# edit variable types
df5$value <- as.numeric(df5$value)

df5$ModelName <- factor(
    df5$ModelName,
    levels = rev(unique(df5$ModelName)),
    ordered = TRUE,
)

df5$Type <- factor(
    df5$Type,
    levels = c("SNPs", "INDELs", "Total"),
)

df5$Phase <- factor(
    df5$Phase,
    levels = unique(df5$Phase),
    ordered = TRUE
)

# Now filter out the Type that we don't want
df5 <- filter(df5, Type != "Total")

# which are the mins
df5 %>%
    group_by(Type) %>%
    slice(which.min(value))

# which are the maxs
df5 %>%
    group_by(Type) %>%
    slice(which.max(value))

# make the ZOOMED IN supplement plot
p <- ggplot(
    data = df5,
    mapping = aes(
        x = value,
        y = ModelName,
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
            "SNPs", 0.985, 1,
            "INDELs", 0.92, 1
        )
    ) + # vary the axis limits
    xlab("F1-Score") + # update x-axis title
    ylab("Model") + # update y-axis title
    scale_fill_brewer(
        palette = "Dark2",
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
    "Supp_GIAB.TestingF1-Score.all_phases.pdf",
    pt = 10, # font size
    sideways = TRUE, # landscape orientation
    w2h = 3.4, # aspect ratio 170mm/50mm
)
grid::grid.draw(g)
invisible(dev.off())

## REMOVE PHASE 5 FOR MAIN BODY OF MANUSCRIPT ---------------##
# remove Phase 5 only
df6 <- dplyr::filter(df5, !grepl(5, Phase))

# make the main plot
p2 <- ggplot(
    data = df6,
    mapping = aes(
        x = value,
        y = ModelName,
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
            "SNPs", 0.985, 1,
            "INDELs", 0.92, 1
        )
    ) + # vary the axis limits
    xlab("F1-Score") + # update x-axis title
    ylab("Model") + # update y-axis title
    scale_fill_brewer(
        palette = "Dark2",
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
    "Fig4_GIAB.TestingF1-Score.phases1-4.pdf",
    pt = 10, # font size
    sideways = TRUE, # landscape orientation
    w2h = 3.4, # aspect ratio 170mm/50mm
)
grid::grid.draw(g2)
invisible(dev.off())
wrapper("end")
