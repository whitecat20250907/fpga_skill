/* Local demonstration interface. GPL-2.0-or-later. */
#ifndef FC_DEMO_CONTROL_H
#define FC_DEMO_CONTROL_H
bool demo_enabled(void);
void demo_endgame_player(int player_id, bool winner);
void demo_draw(cairo_t *cr);
gboolean demo_key(guint key);
gboolean demo_motion(double x, double y);
gboolean demo_click(void);
#endif
