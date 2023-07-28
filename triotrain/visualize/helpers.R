#!/usr/bin/R

load_libraries <- function(lib_list, quiet=TRUE) {
    missing_pkgs <- lib_list[!lib_list %in% installed.packages()]
    for (lib in missing_pkgs) {
        cat(paste("+++ Installing Missing Package: ", lib, " +++ \n"))
        install.packages(
            lib,
            type = "source",
            dependences = TRUE,
            repos = "http://cran.us.r-project.org"
        )
    }

    # Loads a list of ibraries
    load_pkgs <- suppressMessages(sapply(lib_list, require, character = TRUE))
    if (quiet == FALSE) {
        cat("=== Loading Required Packages === \n")
        print(load_pkgs)
    }

    if (length(lib_list) == sum(load_pkgs)) {
        if (quiet == FALSE) { 
            cat("Packages installed correctly!")
        }
    } else {
        stop("!! PACKAGES WERE NOT INSTALLED !!")
    }

}

define_logger <- function() {
    load_libraries("logger")
    logger <- layout_glue_generator(format = "{fn} {time} {level}: {msg}")
    log_layout(logger)
}

wrapper <- function(description) {
    libs <- c("scriptName", "lubridate")
    load_libraries(libs)
    cat(
        "===",
        description,
        "of",
        current_filename(),
        "@",
        as.character(now()),
        "\n"
    )
}

check_phase <- function(itr) {
    if (itr < 1) {
        phase <- 0
    } else if (itr < 7) {
        phase <- 1
    } else if (itr == 7 || itr < 10) {
        phase <- 2
    } else if (itr == 10 || itr < 12) {
        phase <- 3
    } else if (itr == 12 || itr < 15) {
        phase <- 4
    } else {
        phase <- 5
    }
    return(phase)
}