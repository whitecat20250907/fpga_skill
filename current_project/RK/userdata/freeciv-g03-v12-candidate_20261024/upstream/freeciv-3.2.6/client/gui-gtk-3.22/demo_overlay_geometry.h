/* Native demo overlay geometry. GPL-2.0-or-later. */
#ifndef FC_DEMO_OVERLAY_GEOMETRY_H
#define FC_DEMO_OVERLAY_GEOMETRY_H

struct demo_overlay_rect { int x, y, width, height; };

/* Keep the complete measured panel inside the canvas. A canvas smaller than
 * the panel is clipped safely; normal game allocations fit the wrapped text. */
static inline struct demo_overlay_rect
demo_overlay_place(int x, int y, int width, int height,
                   int canvas_width, int canvas_height, int margin)
{
  struct demo_overlay_rect r;
  int mx = canvas_width > margin * 2 ? margin : 0;
  int my = canvas_height > margin * 2 ? margin : 0;
  int available_width = canvas_width - mx * 2;
  int available_height = canvas_height - my * 2;
  if (available_width < 0) available_width = 0;
  if (available_height < 0) available_height = 0;
  r.width = width < available_width ? width : available_width;
  r.height = height < available_height ? height : available_height;
  if (r.width < 0) r.width = 0;
  if (r.height < 0) r.height = 0;
  r.x = x < mx ? mx : x;
  r.y = y < my ? my : y;
  if (r.x > canvas_width - mx - r.width)
    r.x = canvas_width - mx - r.width;
  if (r.y > canvas_height - my - r.height)
    r.y = canvas_height - my - r.height;
  return r;
}

#endif
