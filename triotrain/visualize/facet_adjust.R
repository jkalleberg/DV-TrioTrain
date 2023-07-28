#' Scale individual facet y-axes
#' 
#' 
#' VERY hacky method of imposing facet specific y-axis limits on plots made with facet_wrap
#' Briefly, this function alters an internal function within the ggproto object, 
#' a function which is called to find any limits imposed on the axes of the plot. 
#' We wrap that function in a function of our own, one which intercepts the return 
#' value and modifies it with the axis limits we've specified the parent call
#' 
#' I MAKE NO CLAIMS TO THE STABILITY OF THIS FUNCTION
#' 
#'
#' @param plot The ggproto object to be modified
#' @param ylims A list of tuples specifying the y-axis limits of the individual facets of the plot. 
#' A NULL value in place of a tuple will indicate that the plot should draw that facet as normal (i.e. no axis modification)
#'
#' @return The original plot, with facet y-axes modified as specified
#' @export
#'
#' @examples
#' Not intended to be added to a ggproto call list. 
#' This is a standalone function which accepts a ggproto object
#' and modifies it directly, e.g.
#'
#' YES. GOOD:
#' ======================================
#' plot = ggplot(data, aes(...)) +
#'   geom_whatever() +
#'   geom_thing()
#'
#' scale_individual_facet_y_axes(plot, ylims)
#' ======================================
#'
#' NO. BAD:
#' ======================================
#' ggplot(data, aes(...)) +
#'   geom_whatever() +
#'   geom_thing() +
#'   scale_individual_facet_y_axes(ylims)
#' ======================================
#'
scale_inidividual_facet_y_axes <- function(plot, ylims) {
  init_scales_orig <- plot$facet$init_scales
  init_scales_new <- function(...) {
    r <- init_scales_orig(...)
    # Extract the Y Scale Limits
    y <- r$y
    print(y)
    # If this is not the y axis, then return the original values
    if (is.null(y)) return(r)
    # If these are the y axis limits,
    # then we iterate over them, 
    # replacing them as specified by our ylims parameter
    for (i in seq(1, length(y))) {
      ylim <- ylims[[i]]
      if (!is.null(ylim)) {
        y[[i]]$limits <- ylim
      }
    }
    # Now we reattach the modified Y axis limit 
    # list to the original return object
    r$y <- y
    return(r)
  }
  plot$facet$init_scales <- init_scales_new
  
  return(plot)
}