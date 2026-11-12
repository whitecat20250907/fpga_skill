-- Native Freeciv economy/army rules, not a client-side victory simulation.
campaign_ready = false
campaign_wave = 0
campaign_hotseat = campaign_hotseat or false
function T(x,y) return find.tile(x,y+10) end
local point_income = { ["River Village"]=24, ["Iron Mine"]=32, ["Hill Watch"]=16 }
local enemy_base_x = campaign_hotseat and 17 or 14
if campaign_hotseat then point_income={["River Village"]=10,["Iron Mine"]=10} end
local function add_city(p,x,y,name)
  local tile=T(x,y)
  edit.create_city(p,tile,name)
  local city=tile:city()
  -- Economic sites must survive normal attacks and repeated conquest. This
  -- marker has no movement, defence, production or income bonus of its own.
  -- Bases deliberately remain unmarked and retain native conquest victory.
  if point_income[name] then
    edit.create_extra(tile,"Economic Objective")
    assert(tile:has_extra("Economic Objective"),"Economic objective marker missing")
    log.normal("CAMPAIGN_OBJECTIVE city=%s population_protected=true",name)
  end
  for j=1,2 do
    local settler=edit.create_unit(p,tile,find.unit_type("Settlers"),0,nil,-1)
    edit.perform_action(settler,find.action("Join City"),city)
  end
  edit.create_building(city,find.building_type("Barracks"))
  return city
end
function campaign_turn(turn,year)
  local ps={}
  for p in players_iterate() do ps[#ps+1]=p end
  if not campaign_ready then
    campaign_ready=true
    for _,p in ipairs(ps) do
      local old={};for u in p:units_iterate() do old[#old+1]=u end
      for _,u in ipairs(old) do edit.unit_kill(u,"editor",nil) end
    end
    for i,p in ipairs(ps) do
      for _,name in ipairs({"Bronze Working","Warrior Code","Iron Working","Horseback Riding","Alphabet","Masonry","Mathematics"}) do
        edit.give_tech(p,find.tech_type(name),0,false,"scenario")
      end
      edit.change_gold(p,(i==1 or campaign_hotseat) and 480 or 120)
      local base=add_city(p,i==1 and 7 or enemy_base_x,9,i==1 and "Westwatch" or "Border Keep")
      if i==1 or campaign_hotseat then
        -- The campaign briefing provides geography. Native fog still hides
        -- enemy movements; reveal terrain before any enemy army is created.
        for tile in whole_map_iterate() do edit.tile_show(tile,p) end
        for _,spec in ipairs({{8,9,"Legion"},{8,8,"Horsemen"},{7,10,"Archers"},{6,9,"Catapult"},{7,8,"Legion"}}) do
          -- A pre-existing field army is not all maintained by one size-3
          -- town: native shield upkeep otherwise leaves that town at zero
          -- production. Newly trained units retain their native home city.
          edit.create_unit(p,T(i==1 and spec[1] or 24-spec[1],spec[2]),find.unit_type(spec[3]),1,nil,-1)
        end
        -- A real garrison keeps a first scouting move from exposing the base.
        edit.create_unit(p,base.tile,find.unit_type("Legion"),1,base,-1)
        -- Strategic sites are known; enemy movement still requires scouting.
        for _,xy in ipairs({{10,5},{14,12},{10,13},{enemy_base_x,9}}) do edit.tile_show(T(xy[1],xy[2]),p) end
        if campaign_hotseat then
          local city=add_city(p,i==1 and 10 or 14,i==1 and 5 or 13,i==1 and "River Village" or "Iron Mine")
          edit.create_unit(p,city.tile,find.unit_type("Warriors"),0,city,-1)
        end
      else
        -- The first short campaign has a defended town, not a permanent
        -- opening wall multiplier. AI may still build native improvements.
        for _,name in ipairs({"Phalanx"}) do
          edit.create_unit(p,base.tile,find.unit_type(name),1,base,-1)
        end
        for _,spec in ipairs({{10,5,"River Village","Warriors"},{14,12,"Iron Mine","Phalanx"},{10,13,"Hill Watch","Warriors"}}) do
          local city=add_city(p,spec[1],spec[2],spec[3])
          edit.create_unit(p,city.tile,find.unit_type(spec[4]),0,city,-1)
        end
        edit.create_unit(p,T(15,9),find.unit_type("Warriors"),1,base,-1)
      end
    end
    for _,xy in ipairs({{10,5},{14,12},{10,13},{enemy_base_x,9}}) do edit.tile_show(T(xy[1],xy[2]),ps[1]) end
    log.normal("CAMPAIGN_INIT_V2 points=%d roles=4 fog=true hotseat=%s",campaign_hotseat and 2 or 3,tostring(campaign_hotseat))
  end
  for _,p in ipairs(ps) do
    local income=0
    for city in p:cities_iterate() do income=income+(point_income[city.name] or 0) end
    -- Fixed campaign economy, not a test-time treasury injection. Only the
    -- human campaign side earns objective bonuses; hotseat stays symmetric.
    if not campaign_hotseat then
      if p==ps[1] then
        local home=T(7,9):city()
        if home and home.owner==p then income=income+20 end
      else income=0 end
    end
    if income>0 then
      edit.change_gold(p,income)
      log.normal("CAMPAIGN_INCOME turn=%d player=%s bonus=%d",turn,p.name,income)
    end
  end
  if not campaign_hotseat and turn>=9 and turn%6==3 and ps[2] then
    local enemy=ps[2];local keep=T(enemy_base_x,9):city();local count=0
    for u in enemy:units_iterate() do count=count+1 end
    if keep and keep.owner==enemy and count<8 then
      campaign_wave=campaign_wave+1
      local name=campaign_wave%2==1 and "Horsemen" or "Legion"
      edit.create_unit(enemy,keep.tile,find.unit_type(name),1,keep,-1)
      log.normal("CAMPAIGN_REINFORCE turn=%d wave=%d type=%s",turn,campaign_wave,name)
    end
  end
  return false
end
function campaign_capture(city,old,new,reason)
  if reason=="conquest" then
    log.normal("CAMPAIGN_CAPTURE city=%s owner=%s",city.name,new.name)
    if city.name=="Border Keep" or city.name=="Westwatch" then edit.player_victory(new) end
  end
  return false
end
function campaign_destroy(city,old,destroyer)
  -- Native conquest destroys a size-one city instead of transferring it.
  -- The objective must also finish for that real combat result. Famine,
  -- settler disbanding and other destruction without an enemy do not win.
  if destroyer and destroyer~=old and
     (city.name=="Border Keep" or city.name=="Westwatch") then
    log.normal("CAMPAIGN_BASE_DESTROYED city=%s winner=%s",city.name,destroyer.name)
    edit.player_victory(destroyer)
  end
  return false
end
signal.connect("turn_begin","campaign_turn")
signal.connect("city_transferred","campaign_capture")
signal.connect("city_destroyed","campaign_destroy")
