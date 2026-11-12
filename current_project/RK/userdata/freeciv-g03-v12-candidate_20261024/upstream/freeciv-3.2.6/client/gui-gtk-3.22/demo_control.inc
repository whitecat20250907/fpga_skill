/* Native Freeciv short scenario interface. GPL-2.0-or-later.
 * Included in gui_main.c, reuses the real client's command queue. */
#include <math.h>
#include <gio/gio.h>
#include "citydlg_common.h"
#include "mapview_common.h"
#include "unit.h"
#include "unittype.h"
#include "terrain.h"
#include "movement.h"
#include "combat.h"
#include "actions.h"
#include "pf_tools.h"
#include "goto.h"
#include "chatline_common.h"
#include "demo_control.h"
#include "sprite.h"
#include "demo_input_parse.h"
#include "demo_selection.h"
#include "demo_overlay_geometry.h"
#ifdef GDK_WINDOWING_X11
#include <gdk/gdkx.h>
#endif

enum demo_kind { DEMO_MOVE, DEMO_UNIT, DEMO_CITY, DEMO_PRODUCE, DEMO_BUY, DEMO_RECRUIT, DEMO_BOMBARD, DEMO_GOTO, DEMO_HANDOFF, DEMO_RETURN_MENU, DEMO_MORE=14 };
static const char *demo_types[]={"Legion","Horsemen","Archers","Catapult"};
static const char *demo_roles[]={"步兵 · 守线占点","骑兵 · 机动包抄","弓兵 · 两格支援","攻城 · 高攻低防"};
static int demo_point_income(void) {
  int income=0;
  if(!client_player()) return 0;
  city_list_iterate(client_player()->cities,c) {
    if(!strcmp(city_name_get(c),"River Village")) income+=g_getenv("FREECIV_HOTSEAT")?10:24;
    if(!strcmp(city_name_get(c),"Iron Mine")) income+=g_getenv("FREECIV_HOTSEAT")?10:32;
    if(!strcmp(city_name_get(c),"Hill Watch")) income+=16;
  } city_list_iterate_end;
  return income;
}
struct demo_target { int kind, id, arg; double x,y,ax,ay; char label[96]; };
static struct demo_target demo_targets[64];
static int demo_count, demo_pick=-1, demo_city_id=-1;
static int demo_target_page, demo_target_pages=1;
static guint64 demo_layout_signature;
static bool demo_awake;
static gint64 demo_sample_time;
static struct ds_state demo_selection;
static gint64 demo_source_time;
static GtkWidget *demo_status;
static GtkWidget *demo_sidebar;
static GSocket *demo_socket;
static bool demo_external;
static int demo_seen_turn=-1;
static bool demo_seen_victory;
static guint64 demo_last_event;
static struct unit *demo_unit(void);
static bool demo_has_castle(void);
static int demo_outcome(void);
static bool demo_had_home;
static int demo_native_outcome;
static void demo_sleep(void);
void demo_endgame_player(int player_id, bool winner) {
  if(!demo_enabled() || !client_player() ||
     player_number(client_player())!=player_id) return;
  demo_native_outcome=winner?1:-1;
  demo_sleep();
  if(map_canvas) gtk_widget_queue_draw(map_canvas);
}
static char *demo_published_state;
static int demo_seen_player=-1;
static struct player *demo_handoff_player(void) {
  if(!g_getenv("FREECIV_HOTSEAT") || !client_player()) return NULL;
  players_iterate(p) {
    if(p!=client_player() && p->is_alive && is_human(p) && is_player_phase(p,game.info.phase)) return p;
  } players_iterate_end;
  return NULL;
}
static int demo_range_tiles[64],demo_range_count;
static int demo_range_unit=-1,demo_range_origin=-1,demo_range_moves=-1,demo_range_turn=-1;
static gint64 demo_range_time;
static const char *demo_city_entry_reason="先用下一部队选择守军";

static void demo_update_range(struct unit *u) {
  if(!u || u->moves_left<=0) {demo_range_count=0;return;}
  gint64 now=g_get_monotonic_time();
  if(u->id==demo_range_unit && tile_index(unit_tile(u))==demo_range_origin &&
     u->moves_left==demo_range_moves && game.info.turn==demo_range_turn &&
     now-demo_range_time<250000) return;
  demo_range_unit=u->id;demo_range_origin=tile_index(unit_tile(u));
  demo_range_moves=u->moves_left;demo_range_turn=game.info.turn;demo_range_time=now;
  demo_range_count=0;
  struct pf_parameter parameter;
  pft_fill_unit_parameter(&parameter,&wld.map,u);
  /* Known, peaceful paths only. Combat remains an explicit native target. */
  parameter.get_TB=no_fights_or_unknown;
  struct pf_map *pfm=pf_map_new(&parameter);
  pf_map_positions_iterate(pfm,pos,FALSE) {
    if(pos.total_MC>(unsigned)u->moves_left) break;
    if(demo_range_count<64)
      demo_range_tiles[demo_range_count++]=tile_index(pos.tile);
  } pf_map_positions_iterate_end;
  pf_map_destroy(pfm);
}

/* The city marker intentionally opens recruitment. Its distinct HUD target
 * must use a complete fresh native path, not the 64-tile display cache or
 * send_goto_tile's differently configured (possibly unknown) replacement. */
static struct pf_path *demo_city_entry_path(struct unit *u,struct city *c,
                                           const char **reason) {
  if(reason) *reason="当前不可下达命令";
  if(!client_player() || !can_client_issue_orders() ||
     !is_player_phase(client_player(),game.info.phase) ||
     demo_handoff_player() || demo_outcome()!=0 || client_state()==C_S_OVER)
    return NULL;
  if(!u || unit_owner(u)!=client_player()) {
    if(reason) *reason="先用下一部队选择守军";
    return NULL;
  }
  if(!c || city_owner(c)!=client_player()) {
    if(reason) *reason="仅限己方城市";
    return NULL;
  }
  if(unit_tile(u)==city_tile(c)) {
    if(reason) *reason="当前部队已在此城";
    return NULL;
  }
  if(u->moves_left<=0) {
    if(reason) *reason="当前部队行动力已耗尽";
    return NULL;
  }
  struct pf_parameter parameter;
  pft_fill_unit_parameter(&parameter,&wld.map,u);
  parameter.get_TB=no_fights_or_unknown;
  struct pf_map *pfm=pf_map_new(&parameter);
  struct pf_path *path=pf_map_path(pfm,city_tile(c));
  pf_map_destroy(pfm);
  const struct pf_position *last=path?pf_path_last_position(path):NULL;
  if(!last || last->tile!=city_tile(c) ||
     last->total_MC>(unsigned)u->moves_left) {
    if(path) pf_path_destroy(path);
    if(reason) *reason="本回合无安全可达路径";
    return NULL;
  }
  if(reason) *reason="原生移动进城 · 不自动加防御";
  return path;
}

/* Read-only, event-loop-owned geometry for optional existing-model adapters.
 * Screen coordinates must be transformed through the real map allocation,
 * never through the full monitor or a guessed title/header offset. */
static char *demo_json_label(const char *text) {
  GString *out=g_string_new("");
  for(const char *p=text;*p;p=g_utf8_next_char(p)) {
    gunichar c=g_utf8_get_char(p);
    if(c=='"' || c=='\\')g_string_append_printf(out,"\\%c",(char)c);
    else if(c<32 || c>=127) {
      if(c<=0xffff)g_string_append_printf(out,"\\u%04x",c);
      else {c-=0x10000;g_string_append_printf(out,"\\u%04x\\u%04x",0xd800+(c>>10),0xdc00+(c&1023));}
    } else g_string_append_c(out,(char)c);
  }
  return g_string_free(out,FALSE);
}
static void demo_publish_geometry(void) {
#ifdef GDK_WINDOWING_X11
  gint x,y,mx,my;
  GdkWindow *window=gtk_widget_get_window(toplevel);
  if(!window || !gtk_widget_get_realized(map_canvas) ||
     !GDK_IS_X11_DISPLAY(gtk_widget_get_display(toplevel))) return;
  if(!gdk_window_get_origin(window,&x,&y) ||
     !gtk_widget_translate_coordinates(map_canvas,toplevel,0,0,&mx,&my)) return;
  x+=mx; y+=my;
  struct unit *u=demo_unit();
  GString *state=g_string_new(NULL);
  g_string_printf(state,"{\"version\":1,\"map\":[%d,%d,%d,%d],"
    "\"awake\":%s,\"turn\":%d,\"pick\":%d,\"city\":%d,"
    "\"gold\":%d,\"unit\":%d,\"hp\":%d,\"moves\":%d,"
    "\"point_income\":%d,\"campaign\":2,\"player\":%d,\"phase\":%d,\"handoff\":%d,\"hotseat\":%s,"
    "\"last_event\":\"%" G_GUINT64_FORMAT "\",\"targets\":[",
    x,y,gtk_widget_get_allocated_width(map_canvas),gtk_widget_get_allocated_height(map_canvas),
    demo_awake?"true":"false",game.info.turn,demo_pick,demo_city_id,
    client_player()?client_player()->economic.gold:0,u?u->id:-1,u?u->hp:0,u?u->moves_left:0,demo_point_income(),
    client_player()?player_number(client_player()):-1,game.info.phase,
    demo_handoff_player()?player_number(demo_handoff_player()):-1,g_getenv("FREECIV_HOTSEAT")?"true":"false",
    demo_last_event);
  for(int i=0;i<demo_count;i++) {
    struct demo_target *t=&demo_targets[i];
    struct unit *actor=game_unit_by_number(t->id);
    struct tile *tile=NULL;
    if(t->kind==DEMO_MOVE && actor) tile=mapstep(&wld.map,unit_tile(actor),t->arg);
    else if(t->kind==DEMO_GOTO || t->kind==DEMO_BOMBARD) tile=index_to_tile(&wld.map,t->arg);
    else if(t->kind==DEMO_UNIT && actor) tile=unit_tile(actor);
    else if(t->kind==DEMO_CITY) {
      struct city *city=game_city_by_number(t->id);if(city) tile=city_tile(city);
    }
    struct action *attack=action_by_rule_name("Attack");
    struct unit *defender=tile && actor && attack && t->kind==DEMO_MOVE ? get_defender(&wld.map,actor,tile,attack):NULL;
    if(defender && unit_owner(defender)==client_player()) defender=NULL;
    char *label=demo_json_label(t->label);
    g_string_append_printf(state,"%s{\"kind\":%d,\"id\":%d,\"arg\":%d,\"x\":%d,\"y\":%d,"
      "\"tile\":%d,\"defender\":%d,\"defender_hp\":%d,\"win_chance\":%.6f,\"width\":%d,\"height\":%d,\"label\":\"%s\",\"anchor_x\":%d,\"anchor_y\":%d}",
      i?",":"",t->kind,t->id,t->arg,(int)lround(t->x),(int)lround(t->y),tile?tile_index(tile):-1,
      defender?defender->id:-1,defender?defender->hp:0,defender?unit_win_chance(&wld.map,actor,defender,attack):-1.0,
      (int)(gtk_widget_get_allocated_width(map_canvas)*.23),(int)(gtk_widget_get_allocated_height(map_canvas)*.13),label,(int)t->ax,(int)t->ay);
    g_free(label);
  }
  g_string_append_printf(state,"],\"gaze_protocol\":2,\"selection_ready\":%s,\"selection_confidence\":%.6f,\"selection_margin\":%.6f,\"hover\":%d,\"army\":[",
    ds_confirmable(&demo_selection,g_get_monotonic_time()/1e6)?"true":"false",demo_selection.confidence,demo_selection.margin,
    ds_preview(&demo_selection,g_get_monotonic_time()/1e6));
  int count=0;
  if(client_player()) unit_list_iterate(client_player()->units,member) {
    const char *name=utype_rule_name(unit_type_get(member));
    g_string_append_printf(state,"%s{\"id\":%d,\"type_id\":%d,\"tile\":%d,\"hp\":%d,\"moves\":%d,\"role\":%d}",
      count++?",":"",member->id,utype_number(unit_type_get(member)),tile_index(unit_tile(member)),member->hp,member->moves_left,
      !strcmp(name,"Legion")?0:!strcmp(name,"Horsemen")?1:!strcmp(name,"Archers")?2:!strcmp(name,"Catapult")?3:-1);
  } unit_list_iterate_end;
  g_string_append(state,"],\"cities\":[");count=0;
  if(client_player()) city_list_iterate(client_player()->cities,c) {
    g_string_append_printf(state,"%s{\"id\":%d,\"tile\":%d,\"buy_cost\":%d,\"can_buy\":%s,\"stock\":%d,\"production_type\":%d}",
      count++?",":"",c->id,tile_index(city_tile(c)),c->client.buy_cost,city_can_buy(c)?"true":"false",c->shield_stock,
      c->production.kind==VUT_UTYPE?utype_number(c->production.value.utype):-1);
  } city_list_iterate_end;
  g_string_append_printf(state,"],\"game_over\":%s,\"owns_enemy_base\":%s,\"outcome\":%d,\"known_enemies\":[",
    client_state()==C_S_OVER?"true":"false",demo_has_castle()?"true":"false",demo_outcome());
  count=0;
  /* The client knows only native visibility-filtered enemy units. This is
   * read-only diagnostics, never a server/fog override or another action. */
  players_iterate(other_player) {
    if(other_player==client_player()) continue;
    unit_list_iterate(other_player->units,enemy) {
      g_string_append_printf(state,"%s{\"id\":%d,\"tile\":%d,\"hp\":%d}",
        count++?",":"",enemy->id,tile_index(unit_tile(enemy)),enemy->hp);
    } unit_list_iterate_end;
  } players_iterate_end;
  g_string_append(state,"],\"known_cities\":[");count=0;
  players_iterate(city_player) {
    city_list_iterate(city_player->cities,known_city) {
      gchar *escaped=g_strescape(city_name_get(known_city),NULL);
      g_string_append_printf(state,"%s{\"id\":%d,\"tile\":%d,\"owner\":%d,\"size\":%d,\"name\":\"%s\"}",
        count++?",":"",known_city->id,tile_index(city_tile(known_city)),player_number(city_player),city_size_get(known_city),escaped);
      g_free(escaped);
    } city_list_iterate_end;
  } players_iterate_end;
  g_string_append(state,"]}");
  if(g_strcmp0(demo_published_state,state->str)) {
    gdk_property_change(window,gdk_atom_intern_static_string("_FREECIV_DEMO_STATE_V1"),
      gdk_atom_intern_static_string("UTF8_STRING"),8,GDK_PROP_MODE_REPLACE,
      (const guchar *)state->str,state->len);
    g_free(demo_published_state);demo_published_state=g_strdup(state->str);
  }
  g_string_free(state,TRUE);
#endif
}

bool demo_enabled(void) { return g_getenv("FREECIV_DEMO") != NULL; }
static struct unit *demo_unit(void) {
  return unit_list_size(get_units_in_focus()) ? unit_list_get(get_units_in_focus(),0) : NULL;
}
static bool demo_has_castle(void) {
  bool west=FALSE,east=FALSE;
  if(!client_player()) return FALSE;
  city_list_iterate(client_player()->cities,c) {
    if(!strcmp(city_name_get(c),"Border Keep")) east=TRUE;
    if(!strcmp(city_name_get(c),"Westwatch")) west=TRUE;
  } city_list_iterate_end;
  return east && (!g_getenv("FREECIV_HOTSEAT") || west);
}
static int demo_outcome(void) {
  if(!client_player()) return 0;
  if(demo_native_outcome) return demo_native_outcome;
  if(demo_has_castle()) return 1;
  const char *home=player_number(client_player())==0?"Westwatch":"Border Keep";
  bool owns_home=FALSE;
  city_list_iterate(client_player()->cities,c) {
    if(!strcmp(city_name_get(c),home)) owns_home=TRUE;
  } city_list_iterate_end;
  if(owns_home) demo_had_home=TRUE;
  return demo_had_home && !owns_home ? -1:0;
}
static void demo_sleep(void) {
  demo_awake=FALSE; demo_pick=-1; demo_count=0;
  ds_reset(&demo_selection);demo_sample_time=0;
  if (map_canvas) gtk_widget_queue_draw(map_canvas);
}
static void demo_add(int kind,int id,int arg,double x,double y,const char *label) {
  if (demo_count>=64 || x<20 || y<20 ||
      x>gtk_widget_get_allocated_width(map_canvas)-20 ||
      y>gtk_widget_get_allocated_height(map_canvas)-20) return;
  struct demo_target *t=&demo_targets[demo_count++];
  for(int i=0;i<demo_count-1;i++) {
    if(fabs(demo_targets[i].x-x)<3 && fabs(demo_targets[i].y-y)<3) {
      demo_count--;
      if(kind!=DEMO_CITY) return;
      t=&demo_targets[i]; break;
    }
  }
  t->kind=kind; t->id=id; t->arg=arg; t->x=x; t->y=y; t->ax=x; t->ay=y;
  g_strlcpy(t->label,label,sizeof(t->label));
}
static void demo_tile(int kind,int id,int arg,struct tile *tile,const char *name) {
  float x,y;
  if (tile_to_canvas_pos(&x,&y,map_zoom,tile))
    demo_add(kind,id,arg,x+tileset_tile_width(tileset)*map_zoom/2,
             y+tileset_tile_height(tileset)*map_zoom/2,name);
}
static void demo_collect_raw(void) {
  struct unit *u=demo_unit();
  demo_count=0;
  if(demo_outcome()!=0 || client_state()==C_S_OVER) {
    demo_add(DEMO_RETURN_MENU,0,0,gtk_widget_get_allocated_width(map_canvas)/2,
      190,"返回开始页 · 再玩一局");
    return;
  }
  struct player *handoff=demo_handoff_player();
  if(handoff) {
    demo_add(DEMO_HANDOFF,player_number(handoff),0,gtk_widget_get_allocated_width(map_canvas)/2,
       gtk_widget_get_allocated_height(map_canvas)/2+80,"下一位玩家准备好后确认交接");
    return;
  }
  if (!client_player() || !can_client_issue_orders()) return;
  if (demo_city_id>=0) {
    struct city *c=game_city_by_number(demo_city_id);
    if (!c || city_owner(c)!=client_player()) { demo_city_id=-1; return; }
    double w=gtk_widget_get_allocated_width(map_canvas);
    double h=gtk_widget_get_allocated_height(map_canvas);
    struct pf_path *entry=demo_city_entry_path(u,c,&demo_city_entry_reason);
    if(entry) {
      demo_add(DEMO_GOTO,u->id,tile_index(city_tile(c)),w*.8675,h-191,
               "进入此城 · 集结防守");
      pf_path_destroy(entry);
    }
    for(int i=0;i<4;i++) {
      struct unit_type *ut=unit_type_by_rule_name(demo_types[i]);
      if(ut && can_city_build_unit_now(&wld.map,c,ut))
        demo_add(DEMO_PRODUCE,c->id,i,w*(.115+i*.185),h-94,demo_roles[i]);
    }
    if(city_can_buy(c) && client_player()->economic.gold>=c->client.buy_cost)
      demo_add(DEMO_BUY,c->id,0,w*.88,h-94,"支付金币招募 · 回合结束出兵");
    return;
  }
  city_list_iterate(client_player()->cities,home) {
    demo_add(DEMO_RECRUIT,home->id,0,gtk_widget_get_allocated_width(map_canvas)-132,42,"招募 / 扩军");
    break;
  } city_list_iterate_end;
  demo_update_range(u);
  /* A visible adjacent defender is also a legal Bombard target. Collect
   * support first: semantic targets share tile centers, and demo_add keeps
   * one action at a center. A later melee/move must not hide ranged support. */
  if(u && u->moves_left>0 && !strcmp(utype_rule_name(unit_type_get(u)),"Archers")) {
    struct action *bombard=action_by_rule_name("Bombard");
    if(bombard) square_iterate(&wld.map,unit_tile(u),2,t) {
      if(unit_list_size(t->units) &&
         action_prob_possible(action_prob_vs_stack(&wld.map,u,bombard->id,t)))
        demo_tile(DEMO_BOMBARD,u->id,tile_index(t),t,"弓兵1–2格支援 · 削弱守军");
    } square_iterate_end;
  }
  if (u && u->moves_left>0) {
    for (int d=0;d<8;d++) {
      struct tile *t=mapstep(&wld.map,unit_tile(u),d);
      if (t && can_unit_exist_at_tile(&wld.map,u,t)) {
        struct city *city=tile_city(t);
        struct unit *other=unit_list_size(t->units)?unit_list_get(t->units,0):NULL;
        bool enemy_city=city && city_owner(city)!=client_player();
        bool enemy_unit=other && unit_owner(other)!=client_player();
        if(enemy_unit || enemy_city) {
          struct action *action=action_by_rule_name(enemy_unit?"Attack":"Conquer City");
          if(!action || !action_prob_possible(enemy_unit?
             action_prob_vs_stack(&wld.map,u,action->id,t):action_prob_vs_city(&wld.map,u,action->id,city))) continue;
        } else {
          bool reachable=FALSE;
          for(int i=0;i<demo_range_count;i++) if(demo_range_tiles[i]==tile_index(t)) {reachable=TRUE;break;}
          if(!reachable) continue;
          /* Terrain suitability alone omits ZOC. If the destination needs a
           * legal indirect route, let the native goto execute that route. */
          if(!unit_can_move_to_tile(&wld.map,u,t,FALSE,FALSE,FALSE)) {
            demo_tile(DEMO_GOTO,u->id,tile_index(t),t,"本回合可达 · 原生绕行");continue;
          }
        }
        const char *label=(city && city_owner(city)!=client_player())?"攻占城堡":
          (other && unit_owner(other)!=client_player())?"攻击守军":"移动至此";
        demo_tile(DEMO_MOVE,u->id,d,t,label);
      }
    }
  }
  for(int i=0;i<demo_range_count;i++) {
    struct tile *t=index_to_tile(&wld.map,demo_range_tiles[i]);
    if(t && u && !is_tiles_adjacent(unit_tile(u),t) && t!=unit_tile(u))
      demo_tile(DEMO_GOTO,u->id,tile_index(t),t,"本回合可达 · 原生寻路");
  }
  unit_list_iterate(client_player()->units,other) {
    if (other!=u && other->moves_left>0 && (!u || !is_tiles_adjacent(unit_tile(u),unit_tile(other))))
      demo_tile(DEMO_UNIT,other->id,0,unit_tile(other),utype_name_translation(unit_type_get(other)));
  } unit_list_iterate_end;
  city_list_iterate(client_player()->cities,c) {
    demo_tile(DEMO_CITY,c->id,0,city_tile(c),"城市增援");
  } city_list_iterate_end;
}
/* Separate semantic selection from map density. Every original target remains
 * reachable through paged rails; the native action identity is unchanged. */
static int demo_target_order(const void *aa,const void *bb) {
  const struct demo_target *a=aa,*b=bb;
  if(a->kind!=b->kind)return a->kind<b->kind?-1:1;
  if(a->id!=b->id)return a->id<b->id?-1:1;
  return (a->arg>b->arg)-(a->arg<b->arg);
}
static void demo_collect(void) {
  demo_collect_raw();
  if(!demo_count || demo_targets[0].kind==DEMO_RETURN_MENU || demo_targets[0].kind==DEMO_HANDOFF)return;
  qsort(demo_targets,demo_count,sizeof(demo_targets[0]),demo_target_order);
  guint64 signature=1469598103934665603ULL;
  for(int i=0;i<demo_count;i++) {
    signature=(signature^(guint64)demo_targets[i].kind)*1099511628211ULL;
    signature=(signature^(guint64)demo_targets[i].id)*1099511628211ULL;
    signature=(signature^(guint64)demo_targets[i].arg)*1099511628211ULL;
  }
  if(signature!=demo_layout_signature){demo_target_page=0;demo_layout_signature=signature;}
  int total=demo_count;demo_target_pages=(total+3)/4;
  demo_target_page%=demo_target_pages;
  struct demo_target original[64];memcpy(original,demo_targets,sizeof(original));
  demo_count=0;
  double w=gtk_widget_get_allocated_width(map_canvas),h=gtk_widget_get_allocated_height(map_canvas);
  for(int i=demo_target_page*4;i<MIN(total,(demo_target_page+1)*4);i++) {
    int slot=demo_count;struct demo_target t=original[i];
    t.x=w*(slot%2?.865:.135);t.y=h*(.27+(slot/2)*.40);
    demo_targets[demo_count++]=t;
  }
  if(demo_target_pages>1) {
    char label[96];g_snprintf(label,sizeof(label),"更多目标 · %d / %d",demo_target_page+1,demo_target_pages);
    demo_add(DEMO_MORE,demo_target_page,0,w*.5,h*.9,label);
  }
}
static void demo_sync_selection(void) {
  struct ds_target targets[64];
  demo_collect();
  for(int i=0;i<demo_count;i++) targets[i]=(struct ds_target){demo_targets[i].kind,
    demo_targets[i].id,demo_targets[i].arg,demo_targets[i].x,demo_targets[i].y};
  ds_sync(&demo_selection,targets,demo_count);demo_pick=demo_selection.pick;
}
static void demo_invalidate_targets(void);
static void demo_invalidate(void) {
  demo_invalidate_targets();
  ds_reset(&demo_selection);demo_pick=-1;demo_sample_time=0;
  demo_invalidate_targets();
}
static void demo_sample_at(double x,double y,gint64 stamp,bool filtered) {
  gint64 now=g_get_monotonic_time();
  if (!demo_awake || !isfinite(x) || !isfinite(y)) return;
  if(x<0 || y<0 || x>gtk_widget_get_allocated_width(map_canvas) || y>gtk_widget_get_allocated_height(map_canvas)) {demo_invalidate();return;}
  /* Repaint the previous tooltip before replacing its target or geometry. */
  demo_invalidate_targets();
  demo_sync_selection();
  ds_sample(&demo_selection,x,y,stamp/1e6,now/1e6,filtered);
  demo_pick=demo_selection.pick;demo_sample_time=demo_selection.have_stamp?stamp:0;
  /* Only the old/new overlay bounds change; keep the map surface cached. */
  demo_invalidate_targets();
}
static void demo_sample(double x,double y) {demo_sample_at(x,y,g_get_monotonic_time(),FALSE);}
static void demo_wake(void) {
  if (!can_client_issue_orders() && !demo_handoff_player() && demo_outcome()==0 && client_state()!=C_S_OVER) return;
  demo_awake=TRUE; demo_pick=-1; demo_sample_time=0; demo_collect();
  ds_reset(&demo_selection);
  gtk_widget_queue_draw(map_canvas);
}
static void demo_confirm(void) {
  gint64 now=g_get_monotonic_time();
  if(demo_awake) demo_sync_selection(); /* Recheck identity/geometry/action availability at execution. */
  if (!demo_awake || demo_pick<0 || demo_pick>=demo_count ||
      !ds_confirmable(&demo_selection,now/1e6) ||
      (!can_client_issue_orders() && demo_targets[demo_pick].kind!=DEMO_HANDOFF && demo_targets[demo_pick].kind!=DEMO_RETURN_MENU)) return;
  struct demo_target t=demo_targets[demo_pick];
  int entry_city_id=t.kind==DEMO_GOTO?demo_city_id:-1;
  demo_sleep();
  if(t.kind==DEMO_MORE) {demo_target_page=(t.id+1)%demo_target_pages;gtk_widget_queue_draw(map_canvas);return;}
  if(t.kind==DEMO_RETURN_MENU) {
    start_quitting();if(client.conn.used) disconnect_from_server(FALSE);
    quit_gtk_main();return;
  }
  if(t.kind==DEMO_HANDOFF) {
    struct player *p=demo_handoff_player();
    demo_sample_time=0;demo_city_id=-1;
    if(p && player_number(p)==t.id) send_chat_printf("/take \"%s\"",player_name(p));
    return;
  }
  struct unit *u=game_unit_by_number(t.id);
  if(t.kind==DEMO_MOVE && u && unit_owner(u)==client_player() && u->moves_left>0)
    request_move_unit_direction(u,t.arg);
  else if(t.kind==DEMO_UNIT && u && unit_owner(u)==client_player()) unit_focus_set_and_select(u);
  else if(t.kind==DEMO_CITY || t.kind==DEMO_RECRUIT) { demo_city_id=t.id; }
  else if(t.kind==DEMO_BOMBARD && u && unit_owner(u)==client_player()) {
    struct action *a=action_by_rule_name("Bombard");
    struct tile *tile=index_to_tile(&wld.map,t.arg);
    if(a && tile && action_prob_possible(action_prob_vs_stack(&wld.map,u,a->id,tile)))
      request_do_action(a->id,u->id,t.arg,0,"");
  }
  else if(t.kind==DEMO_GOTO && u && unit_owner(u)==client_player() && u->moves_left>0) {
    struct tile *tile=index_to_tile(&wld.map,t.arg);
    if(entry_city_id>=0) {
      struct city *c=game_city_by_number(entry_city_id);
      struct pf_path *path=c && city_tile(c)==tile && demo_unit()==u?
        demo_city_entry_path(u,c,NULL):NULL;
      if(path) {
        send_goto_path(u,path,NULL);
        pf_path_destroy(path);
        demo_city_id=-1;
      }
    } else if(tile) send_goto_tile(u,tile);
  }
  else if(t.kind==DEMO_PRODUCE || t.kind==DEMO_BUY) {
    struct city *c=game_city_by_number(t.id);
    if(c && city_owner(c)==client_player()) {
      if(t.kind==DEMO_BUY) city_buy_production(c);
      else {
        struct universal v; v.kind=VUT_UTYPE;
        v.value.utype=t.arg>=0&&t.arg<4?unit_type_by_rule_name(demo_types[t.arg]):NULL;
        if(v.value.utype) city_change_production(c,&v);
      }
    }
    /* Confirmation sleeps selection, while the visible recruitment panel
     * remains available for the next wake/confirm purchase. */
  }
  gtk_widget_queue_draw(map_canvas);
}
static void demo_next_unit(void) {
  if(!client_player() || !can_client_issue_orders()) return;
  struct unit *current=demo_unit(),*first=NULL,*next=NULL;
  int current_id=current?current->id:-1;
  /* The native automatic-focus heuristic skips done/goto and city-stack
   * units. The demonstration's explicit Next action must still let the
   * player select every owned unit which has native moves remaining. */
  unit_list_iterate(client_player()->units,member) {
    if(member->moves_left<=0) continue;
    if(!first || member->id<first->id) first=member;
    if(member->id>current_id && (!next || member->id<next->id)) next=member;
  } unit_list_iterate_end;
  if(next || first) unit_focus_set_and_select(next?next:first);
}
gboolean demo_key(guint key) {
  if(!demo_enabled() || !can_client_change_view()) return FALSE;
  switch(key) {
  case GDK_KEY_F1: if(demo_awake) demo_sleep(); else demo_wake(); break;
  case GDK_KEY_space: demo_confirm(); break;
  case GDK_KEY_Escape: demo_city_id=-1;demo_sleep();break;
  case GDK_KEY_Tab: demo_city_id=-1;demo_sleep();demo_next_unit();break;
  case GDK_KEY_Return: demo_city_id=-1;demo_sleep();key_end_turn();break;
  default: break;
  }
  return TRUE;
}
gboolean demo_motion(double x,double y) {
  if(!demo_enabled()) return FALSE;
  if(!demo_external) demo_sample(x,y);
  return TRUE;
}
gboolean demo_click(void) { if(demo_enabled()) {gtk_widget_grab_focus(map_canvas);return TRUE;} return FALSE; }
static void demo_text(cairo_t *cr,double x,double y,const char *text,int size) {
  PangoLayout *p=pango_cairo_create_layout(cr);
  PangoFontDescription *font=pango_font_description_from_string("Sans");
  pango_font_description_set_absolute_size(font,size*PANGO_SCALE);
  pango_layout_set_font_description(p,font);pango_layout_set_text(p,text,-1);
  cairo_move_to(cr,x,y);pango_cairo_show_layout(cr,p);
  pango_font_description_free(font);g_object_unref(p);
}

struct demo_tooltip {
  PangoLayout *layout;
  struct demo_overlay_rect bounds;
  int text_x, text_y;
};
/* Hysteresis can briefly show a retained choice and a different preview. */
static struct demo_overlay_rect demo_last_tooltips[2];
static int demo_last_tooltip_count;

/* A single measured panel keeps the risk line in the same redraw footprint
 * as its action and readiness labels. Ink may extend outside logical bounds. */
static struct demo_tooltip demo_make_tooltip(const struct demo_target *t,
                                            bool chosen) {
  enum { padding=8, margin=8 };
  int w=gtk_widget_get_allocated_width(map_canvas);
  int h=gtk_widget_get_allocated_height(map_canvas);
  char risk[160]="",text[384];
  struct unit *attacker=game_unit_by_number(t->id);
  if(t->kind==DEMO_MOVE && attacker) {
    struct tile *tile=mapstep(&wld.map,unit_tile(attacker),t->arg);
    struct action *attack=action_by_rule_name("Attack");
    struct unit *defender=tile&&attack?get_defender(&wld.map,attacker,tile,attack):NULL;
    if(defender && unit_owner(defender)!=client_player()) {
      double chance=unit_win_chance(&wld.map,attacker,defender,attack);
      g_snprintf(risk,sizeof(risk),"\n敌军 HP %d · 预计胜率 %.0f%% · %s",
        defender->hp,100*chance,chance<.45?"高风险":"可评估进攻");
    }
  }
  g_snprintf(text,sizeof(text),"%s\n%s%s",t->label,chosen?"可确认":"定位中",risk);
  struct demo_tooltip tip;
  tip.layout=gtk_widget_create_pango_layout(map_canvas,text);
  PangoFontDescription *font=pango_font_description_from_string("Sans");
  pango_font_description_set_absolute_size(font,13*PANGO_SCALE);
  pango_layout_set_font_description(tip.layout,font);
  pango_font_description_free(font);
  PangoRectangle ink,logical;
  pango_layout_get_pixel_extents(tip.layout,&ink,&logical);
  int content_width=MAX(1,w-2*(margin+padding));
  int left=MIN(ink.x,logical.x),top=MIN(ink.y,logical.y);
  int right=MAX(ink.x+ink.width,logical.x+logical.width);
  if(right-left>content_width) {
    pango_layout_set_width(tip.layout,content_width*PANGO_SCALE);
    pango_layout_set_wrap(tip.layout,PANGO_WRAP_WORD_CHAR);
    pango_layout_get_pixel_extents(tip.layout,&ink,&logical);
    left=MIN(ink.x,logical.x);top=MIN(ink.y,logical.y);
    right=MAX(ink.x+ink.width,logical.x+logical.width);
  }
  int bottom=MAX(ink.y+ink.height,logical.y+logical.height);
  int panel_width=right-left+padding*2,panel_height=bottom-top+padding*2;
  int x=(int)lround(t->x)+34,y=(int)lround(t->y)-32;
  if(x+panel_width>w-margin) x=(int)lround(t->x)-34-panel_width;
  tip.bounds=demo_overlay_place(x,y,panel_width,panel_height,w,h,margin);
  tip.text_x=tip.bounds.x+padding-left;
  tip.text_y=tip.bounds.y+padding-top;
  return tip;
}
static void demo_queue_overlay(struct demo_overlay_rect bounds) {
  if(bounds.width>0 && bounds.height>0)
    gtk_widget_queue_draw_area(map_canvas,bounds.x,bounds.y,bounds.width,bounds.height);
}
static void demo_invalidate_target(const struct demo_target *t,bool active,bool chosen) {
  int w=gtk_widget_get_allocated_width(map_canvas);
  int h=gtk_widget_get_allocated_height(map_canvas);
  demo_queue_overlay(demo_overlay_place((int)floor(t->x)-34,(int)floor(t->y)-34,
                                       69,69,w,h,0));
  demo_queue_overlay(demo_overlay_place((int)(t->x-w*.11)-4,(int)(t->y-h*.055)-4,(int)(w*.22)+8,(int)(h*.11)+8,w,h,0));
  if(active) {
    demo_queue_overlay(demo_overlay_place((int)MIN(t->x,t->ax)-24,(int)MIN(t->y,t->ay)-24,(int)fabs(t->x-t->ax)+49,(int)fabs(t->y-t->ay)+49,w,h,0));
    struct demo_tooltip tip=demo_make_tooltip(t,chosen);
    demo_queue_overlay(tip.bounds);g_object_unref(tip.layout);
  }
}
static void demo_invalidate_targets(void) {
  if(!map_canvas) return;
  /* This saved rectangle also erases a tooltip whose sample just expired. */
  for(int i=0;i<demo_last_tooltip_count;i++) demo_queue_overlay(demo_last_tooltips[i]);
  if(!demo_awake) return;
  double now=g_get_monotonic_time()/1e6;
  int hover=ds_preview(&demo_selection,now);
  bool ready=ds_confirmable(&demo_selection,now);
  for(int i=0;i<demo_count;i++) {
    bool chosen=i==demo_pick && ready;
    demo_invalidate_target(&demo_targets[i],chosen || i==hover,chosen);
  }
}
static void demo_draw_tooltip(cairo_t *cr,const struct demo_target *t,bool chosen) {
  struct demo_tooltip tip=demo_make_tooltip(t,chosen);
  cairo_save(cr);
  cairo_rectangle(cr,tip.bounds.x,tip.bounds.y,tip.bounds.width,tip.bounds.height);
  cairo_clip(cr);
  cairo_set_source_rgba(cr,.063,.075,.094,.96);cairo_paint(cr);
  cairo_set_source_rgb(cr,chosen?1:.6,.9,chosen?.65:1.);
  cairo_move_to(cr,tip.text_x,tip.text_y);pango_cairo_show_layout(cr,tip.layout);
  cairo_restore(cr);
  if(demo_last_tooltip_count<2) demo_last_tooltips[demo_last_tooltip_count++]=tip.bounds;
  g_object_unref(tip.layout);
}
void demo_draw(cairo_t *cr) {
  if(!demo_enabled() || !can_client_change_view()) return;
  demo_last_tooltip_count=0;
  int outcome=demo_outcome();
  struct player *handoff=outcome==0?demo_handoff_player():NULL;
  if(handoff) {
    double w=gtk_widget_get_allocated_width(map_canvas),h=gtk_widget_get_allocated_height(map_canvas);
    cairo_set_source_rgba(cr,.063,.075,.094,1);cairo_paint(cr);
    cairo_set_source_rgb(cr,.898,.722,.471);char title[128];
    g_snprintf(title,sizeof(title),"双人轮战 · 请交给玩家 %d",player_number(handoff)+1);
    demo_text(cr,w/2-245,h/2-72,title,32);
    cairo_set_source_rgb(cr,.678,.718,.761);
    demo_text(cr,w/2-300,h/2-10,"下一位玩家准备好后，唤起并确认中心交接目标",20);
    demo_text(cr,w/2-300,h/2+26,"交接前遮住地图；交接后休眠，需重新唤起操作",18);
    cairo_set_source_rgb(cr,.125,.235,.263);cairo_rectangle(cr,w/2-220,h/2+54,440,56);cairo_fill(cr);
    cairo_set_source_rgb(cr,.95,.94,.85);demo_text(cr,w/2-160,h/2+68,"确认交接 · 接管原生玩家",21);
    if(!demo_awake) return;
  }
  if(client_player() && !handoff) {
    double w=gtk_widget_get_allocated_width(map_canvas);
    cairo_set_source_rgba(cr,.094,.114,.141,.96);cairo_rectangle(cr,18,12,w-36,64);cairo_fill(cr);
    cairo_set_source_rgb(cr,.929,.941,.953);char economy[320];
    g_snprintf(economy,sizeof(economy),"国库 %d 金币   争夺点 +%d/回合   %s占点赚钱 → 招兵扩军 → 攻城获胜",
       client_player()->economic.gold,demo_point_income(),g_getenv("FREECIV_HOTSEAT")?"":"基地供给 +20/回合   ");
    demo_text(cr,32,24,economy,17);
    cairo_set_source_rgb(cr,.125,.235,.263);cairo_rectangle(cr,w-237,19,210,46);cairo_fill(cr);
    cairo_set_source_rgb(cr,.929,.941,.953);demo_text(cr,w-210,28,"招募 / 扩军",20);
  }
  if(client_player() && !handoff) {
    if(outcome!=0) {
      double w=gtk_widget_get_allocated_width(map_canvas);
      cairo_set_source_rgba(cr,.04,.09,.08,.95);cairo_rectangle(cr,w/2-330,35,660,105);cairo_fill(cr);
      cairo_set_source_rgb(cr,.94,.82,.48);
      demo_text(cr,w/2-290,48,outcome>0?"战役胜利 · 敌方基地已攻克":"防守失败 · 己方基地已失守",30);
      demo_text(cr,w/2-290,98,"F1 唤起 · 指向下方按钮 · Space 返回开始页",17);
      cairo_set_source_rgb(cr,.125,.235,.263);cairo_rectangle(cr,w/2-190,160,380,60);cairo_fill(cr);
      cairo_set_source_rgb(cr,.929,.941,.953);demo_text(cr,w/2-140,176,"返回开始页 · 再玩一局",22);
    }
  }
  if(demo_city_id>=0) {
    double w=gtk_widget_get_allocated_width(map_canvas);
    struct city *c=game_city_by_number(demo_city_id);demo_collect();
    cairo_set_source_rgba(cr,.094,.114,.141,.96);cairo_rectangle(cr,w*.26,80,w*.48,90);cairo_fill(cr);
    char info[256];g_snprintf(info,sizeof(info),"招募 · %s · 国库 %d 金币",c?city_name_get(c):"",client_player()->economic.gold);
    cairo_set_source_rgb(cr,.898,.722,.471);demo_text(cr,w*.28,92,info,19);
    g_snprintf(info,sizeof(info),"当前费用 %d · 选择兵种后支付 · 结束回合出兵",c?c->client.buy_cost:0);
    demo_text(cr,w*.28,129,info,14);
  }
  if(!demo_awake) return;
  if(demo_city_id<0) {
    cairo_set_source_rgba(cr,.094,.114,.141,.94);cairo_rectangle(cr,22,82,500,27);cairo_fill(cr);
    cairo_set_source_rgb(cr,.678,.718,.761);
    demo_text(cr,32,86,"两侧选择目标 · 高亮连线对应地图 · 更多目标可翻页",13);
  }
  for(int i=0;i<demo_count;i++) {
    struct demo_target *t=&demo_targets[i];double now=g_get_monotonic_time()/1e6;
    bool hovering=i==ds_preview(&demo_selection,now),chosen=i==demo_pick && ds_confirmable(&demo_selection,now);
    double w=gtk_widget_get_allocated_width(map_canvas),h=gtk_widget_get_allocated_height(map_canvas);
    double bw=w*.23,bh=h*.13;
    /* Numbered map anchors are annotations, never extra snapping targets. */
    if(t->kind==DEMO_MOVE || t->kind==DEMO_UNIT || t->kind==DEMO_CITY || t->kind==DEMO_GOTO || t->kind==DEMO_BOMBARD) {
      char marker[12];g_snprintf(marker,sizeof(marker),"%02d",demo_target_page*4+i+1);
      cairo_new_path(cr);cairo_set_source_rgba(cr,.094,.114,.141,.96);cairo_arc(cr,t->ax,t->ay,15,0,2*G_PI);cairo_fill_preserve(cr);
      cairo_set_source_rgba(cr,.486,.788,.824,.9);cairo_set_line_width(cr,1.3);cairo_stroke(cr);
      cairo_set_source_rgb(cr,.95,.97,.94);demo_text(cr,t->ax-10,t->ay-9,marker,11);
    }
    if((chosen||hovering) && (fabs(t->ax-t->x)>1 || fabs(t->ay-t->y)>1)) {
      cairo_set_source_rgba(cr,.486,.788,.824,.8);cairo_set_line_width(cr,1.5);
      cairo_move_to(cr,t->x,t->y);cairo_line_to(cr,t->ax,t->ay);cairo_stroke(cr);
      cairo_arc(cr,t->ax,t->ay,20,0,2*G_PI);cairo_stroke(cr);
    }
    cairo_set_source_rgba(cr,chosen?.20:.094,chosen?.17:.114,chosen?.12:.141,.97);
    cairo_rectangle(cr,t->x-bw/2,t->y-bh/2,bw,bh);cairo_fill_preserve(cr);
    cairo_set_source_rgba(cr,chosen?.898:.486,chosen?.722:.788,chosen?.471:.824,hovering||chosen?1:.45);
    cairo_set_line_width(cr,chosen||hovering?3:1);cairo_stroke(cr);
    char number[80];g_snprintf(number,sizeof(number),"%02d    %s",demo_target_page*4+i+1,chosen?"可确认":hovering?"定位中":"选择目标");
    cairo_set_source_rgb(cr,.678,.718,.761);demo_text(cr,t->x-bw/2+16,t->y-bh/2+10,number,11);
    cairo_set_source_rgb(cr,.929,.941,.953);demo_text(cr,t->x-bw/2+16,t->y+2,t->label,18);
  }
  /* Paint text after every ring so a neighbouring target cannot cross it. */
  double tooltip_now=g_get_monotonic_time()/1e6;
  int tooltip_hover=ds_preview(&demo_selection,tooltip_now);
  bool tooltip_ready=ds_confirmable(&demo_selection,tooltip_now);
  for(int i=0;i<demo_count;i++) {
    bool chosen=i==demo_pick && tooltip_ready;
    if(chosen || i==tooltip_hover) demo_draw_tooltip(cr,&demo_targets[i],chosen);
  }
}
static gboolean demo_tick(gpointer unused) {
  if(!can_client_change_view()) return G_SOURCE_CONTINUE;
  bool won=demo_outcome()!=0;
  int current_player=client_player()?player_number(client_player()):-1;
  if(current_player!=demo_seen_player) {
    demo_seen_player=current_player;demo_city_id=-1;demo_sample_time=0;demo_seen_turn=-1;demo_range_time=0;
    demo_sleep();
  }
  if(won!=demo_seen_victory) {
    demo_seen_victory=won;
    gtk_widget_queue_draw_area(map_canvas,
      gtk_widget_get_allocated_width(map_canvas)/2-330,35,660,105);
  }
  if(game.info.turn!=demo_seen_turn) {
    if(demo_seen_turn<0) {
      gtk_widget_grab_focus(map_canvas);
      struct tile *center=native_pos_to_tile(&wld.map,10,19);
      if(center) center_tile_mapcanvas(center);
    }
    demo_seen_turn=game.info.turn;demo_city_id=-1;demo_sleep();
  }
  if(demo_socket) for(int i=0;i<32;i++) {
    char buf[160]; GError *err=NULL;GSocketAddress *sender=NULL;
    gssize n=g_socket_receive_from(demo_socket,&sender,buf,sizeof(buf)-1,NULL,&err);
    if(n<=0) {g_clear_object(&sender);g_clear_error(&err);break;}
    if(n==sizeof(buf)-1 || memchr(buf,0,n)) {g_clear_object(&sender);continue;}
    buf[n]=0;
    char nonce[33],extra;
    if(sscanf(buf,"query %32[0-9a-f]%c",nonce,&extra)==1 && strlen(nonce)==32) {
      if(demo_published_state && sender) {
        char *reply=g_strdup_printf("state %s %s",nonce,demo_published_state);
        g_socket_send_to(demo_socket,sender,reply,strlen(reply),NULL,NULL);
        g_free(reply);
      }
      g_clear_object(&sender);
      continue;
    }
    g_clear_object(&sender);
    double x,y;
    if(!strncmp(buf,"gaze",4)) {
      demo_external=TRUE;
      gint64 stamp=0,now=g_get_monotonic_time();
      if(!strcmp(buf,"gaze_lost")) demo_invalidate();
      else if(!strncmp(buf,"gaze2 ",6)) {
        if(!demo_parse_gaze2(buf,now,&stamp,&x,&y)) demo_invalidate();
        else if(stamp>demo_source_time) {
          demo_source_time=stamp;
          demo_sample_at(x*gtk_widget_get_allocated_width(map_canvas),y*gtk_widget_get_allocated_height(map_canvas),stamp,TRUE);
        }
      } else if(sscanf(buf,"gaze %lf %lf %c",&x,&y,&extra)==2 && isfinite(x) && isfinite(y) &&
         x>=0 && x<=1 && y>=0 && y<=1)
        demo_sample(x*gtk_widget_get_allocated_width(map_canvas),y*gtk_widget_get_allocated_height(map_canvas));
      else demo_invalidate();
    } else {
      guint64 seq; char action[24];
      if(demo_parse_event(buf,&seq,action) && seq>demo_last_event) {
        demo_last_event=seq;
        if(!strcmp(action,"wake")) demo_wake();
        else if(!strcmp(action,"confirm")) demo_confirm();
        else if(!strcmp(action,"cancel")) demo_key(GDK_KEY_Escape);
        else if(!strcmp(action,"next")) demo_key(GDK_KEY_Tab);
        else if(!strcmp(action,"end")) demo_key(GDK_KEY_Return);
        else if(!strcmp(action,"mouse")) demo_external=FALSE;
      }
    }
  }
  if(demo_awake && demo_sample_time && g_get_monotonic_time()-demo_sample_time>250000) demo_invalidate();
  if(demo_awake && !demo_external && gtk_widget_get_window(map_canvas)) {
    GdkDisplay *display=gtk_widget_get_display(map_canvas);
    GdkDevice *pointer=gdk_seat_get_pointer(gdk_display_get_default_seat(display));
    gint x,y; gdk_window_get_device_position(gtk_widget_get_window(map_canvas),pointer,&x,&y,NULL);
    demo_sample(x,y);
  }
  if(demo_status) {
    struct unit *u=demo_unit();char s[512],details[128];
    if(u) g_snprintf(details,sizeof(details),"%s · 生命 %d · 行动力 %.1f",utype_name_translation(unit_type_get(u)),u->hp,u->moves_left/3.0);
    else g_strlcpy(details,"部队行动完毕",sizeof(details));
    g_snprintf(s,sizeof(s),"%s · 玩家 %d   ·   第 %d 回合   ·   %s   ·   %s\nF1 唤起视线    Space 确认    Esc 取消    Tab 下一部队    Enter 结束回合",
      g_getenv("FREECIV_HOTSEAT")?"双人轮战：攻占对方基地":"单人战役：攻占 Border Keep",current_player+1,game.info.turn,
      details,
      demo_awake?"选择中：指向侧边目标后确认":"视线休眠：普通注视不操作");
    if(strcmp(gtk_label_get_text(GTK_LABEL(demo_status)),s)) gtk_label_set_text(GTK_LABEL(demo_status),s);
  }
  demo_publish_geometry();
  return G_SOURCE_CONTINUE;
}
static void demo_setup(void) {
  if(!demo_enabled()) return;
  gtk_window_set_title(GTK_WINDOW(toplevel),"Freeciv · 边境战役 · 占点 / 招募 / 攻防");
  gtk_window_fullscreen(GTK_WINDOW(toplevel));
  demo_status=gtk_label_new("边境要塞：夺取东侧城堡");
  gtk_widget_set_size_request(demo_status,-1,68);
  gtk_grid_attach_next_to(GTK_GRID(top_vbox),demo_status,NULL,GTK_POS_TOP,1,1);
  gtk_widget_show(demo_status);
  gtk_widget_hide(avbox);gtk_widget_set_no_show_all(avbox,TRUE);
  gtk_widget_hide(bottom_notebook);gtk_widget_set_no_show_all(bottom_notebook,TRUE);
  if(main_menubar) {gtk_widget_hide(main_menubar);gtk_widget_set_no_show_all(main_menubar,TRUE);}
  gtk_notebook_set_show_tabs(GTK_NOTEBOOK(top_notebook),FALSE);
  gui_options.popup_new_cities=FALSE;
  gui_options.popup_attack_actions=FALSE;
  gui_options.auto_center_on_unit=FALSE;
  gui_options.auto_center_each_turn=FALSE;
  GUI_GTK_OPTION(popup_tech_help)=GUI_POPUP_TECH_HELP_DISABLED;
  GtkCssProvider *css=gtk_css_provider_new();
  gtk_css_provider_load_from_data(css,"* { background-image: none; font-family: Sans; font-size: 15px; } window, grid, notebook, label { background-color: #172126; color: #e7dfcd; } label { padding: 5px; }",-1,NULL);
  gtk_style_context_add_provider_for_screen(gtk_widget_get_screen(toplevel),GTK_STYLE_PROVIDER(css),GTK_STYLE_PROVIDER_PRIORITY_USER);
  g_object_unref(css);
  GError *err=NULL;
  demo_socket=g_socket_new(G_SOCKET_FAMILY_IPV4,G_SOCKET_TYPE_DATAGRAM,G_SOCKET_PROTOCOL_UDP,&err);
  if(demo_socket) {
    GInetAddress *ip=g_inet_address_new_loopback(G_SOCKET_FAMILY_IPV4);
    GSocketAddress *address=g_inet_socket_address_new(ip,29778);
    if(!g_socket_bind(demo_socket,address,FALSE,&err)) {g_object_unref(demo_socket);demo_socket=NULL;}
    else g_socket_set_blocking(demo_socket,FALSE);
    g_object_unref(address);g_object_unref(ip);
  }
  if(err) {log_error("Demo input: %s",err->message);g_clear_error(&err);}
  g_timeout_add(40,demo_tick,NULL);
}
