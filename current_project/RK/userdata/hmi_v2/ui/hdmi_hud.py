"""Click-through XShape HUD. No input focus, input injection or hardware access."""
import sys,time
from core.config import load,ROOT
from core.clock import fresh
from core.hmibus import Subscriber
from core.service import Service
from ui.feedback import feedback
from ui.operation_card import card as operation_card, placement as operation_placement
from ui.calibration_feedback import scorecard
from ui.live_preview import LivePreview, Rate, position, compact_status, compact_receipt

def main():
    c=load();sys.path.insert(0,str(ROOT/'vendor/gaze_app'))
    import pygame
    import cv2
    cv2.setNumThreads(1)
    from desktop_input import display_geometry,chinese_font
    from Xlib import X,display
    from Xlib.ext import shape
    geo=display_geometry(c['display']['hdmi']);d=display.Display();screen=d.screen();root=screen.root
    if not d.has_extension('SHAPE'):raise RuntimeError('XShape is required for a click-through HUD')
    pygame.font.init();font=pygame.font.Font(chinese_font(),20)
    mini_font=pygame.font.Font(chinese_font(),16);metric_font=pygame.font.Font(chinese_font(),13)
    panel_width=max(192,min(288,round(geo['width']*.15)//16*16));image_height=round(panel_width*9/16);panel_height=image_height+28
    def window(w,h):
        win=root.create_window(0,0,w,h,0,screen.root_depth,X.InputOutput,X.CopyFromParent,background_pixel=0x181d24,override_redirect=True,event_mask=X.ExposureMask)
        win.shape_rectangles(shape.SO.Set,shape.SK.Input,X.Unsorted,0,0,[])
        return win,win.create_gc()
    def put_surface(win,gc,surface):
        w,h=surface.get_size()
        # Stay below the core X11 request limit while batching pixel rows.
        rows=max(1,min(128,((d.display.info.max_request_length*4)-64)//(w*4)))
        for y in range(0,h,rows):
            tile=surface.subsurface((0,y,w,min(rows,h-y)))
            win.put_image(gc,0,y,w,tile.get_height(),X.ZPixmap,screen.root_depth,0,pygame.image.tobytes(tile,'BGRA'))
    pill,gc=window(panel_width,panel_height);cursor,cgc=window(32,32);menu,mgc=window(440,460)
    pill.set_wm_name('HMI Live Preview');menu.set_wm_name('HMI Menu');cursor.set_wm_name('HMI Target')
    operation_width=min(440,max(320,geo['width']//4));operation_height=126
    operation,ogc=window(operation_width,operation_height);operation.set_wm_name('HMI Operation');last_operation=None
    # Bounding shape is a ring; its input shape remains empty.
    rects=[]
    for y in range(32):
        for x in range(32):
            radius=(x-15.5)**2+(y-15.5)**2
            if 100<=radius<=225:rects.append((x,y,1,1))
    cursor.shape_rectangles(shape.SO.Set,shape.SK.Bounding,X.Unsorted,0,0,rects)
    svc=Service('hud',c);sub=Subscriber(['hmi.state','vision.face','sys.metrics'],run=c['paths']['run']);last=None
    preview=LivePreview(c['paths']['run']);display_rate=Rate();display_hz=None;draw_count=0;last_draw=0;last_image_serial=None
    seen_toast=None;receipt='';receipt_until=0
    try:
        while svc.running:
            # X can discard obscured pixels when another full-screen app is
            # mapped. Static-state caching must not suppress Expose repaint.
            while d.pending_events():
                if d.next_event().type==X.Expose:last=None;last_operation=None
            sub.poll(30);state=sub.latest('hmi.state') or {};now=time.monotonic_ns()
            connected=fresh(state.get('src_ns'),350,now)
            if not connected:
                # Do not replay old engine state; keep a visible connection status.
                state=dict(state,state='DEGRADED',cursor={},target_session={},menu={},calib={},participants={},shortcut=None)
            show_preview = state.get('context') != 'BASIC' or state.get('state') == 'CALIBRATING'
            read_started=now
            if show_preview:preview.read(now,state.get('epoch'))
            now=time.monotonic_ns();read_ms=(now-read_started)/1e6
            preview.metrics(sub.latest('sys.metrics.gaze') or {},state.get('epoch'),now)
            face=sub.latest('vision.face') or {}
            if state.get('toast')!=seen_toast:
                seen_toast=state.get('toast');receipt=compact_receipt(seen_toast);receipt_until=now+3_000_000_000
            status=(receipt if receipt and now<receipt_until else compact_status(state)) if connected else '交互连接中'
            info=feedback(state)
            card=scorecard(state.get('calib',{})) if state.get('state')=='CALIBRATING' else None
            show_preview = state.get('context') != 'BASIC' or state.get('state') == 'CALIBRATING'
            visual={'show_preview':show_preview,'status':status,'image':preview.frame.serial if show_preview and preview.frame else None,
                    'image_valid':show_preview and preview.valid(now,state.get('epoch')),'face':face.get('seq') if show_preview else None,
                    'operation':operation_card(state,receipt if now<receipt_until else ''),
                    'metrics':(round(preview.source_hz or 0),round(preview.face_hz or 0)),'card':card,'state':state.get('state'),'menu':state.get('menu'),
                    'onboard':state.get('onboard'),'shortcut':state.get('shortcut'),
                    'target':state.get('calib',{}).get('target') if state.get('state')=='CALIBRATING' else None,
                    'registration':state.get('participants') if state.get('participants',{}).get('registration') else None,
                    'blink':int(now/300_000_000)%2 if state.get('state')=='POINTING' else 1,
                    'cursor':{k:state.get('cursor',{}).get(k) for k in ('xy','frozen')} if state.get('target_session',{}).get('phase') in ('SELECTING','LOCKED') else None}
            if visual!=last and now-last_draw>=50_000_000:
                last=visual;last_draw=now
                def fit(text,font,limit):
                    text=str(text)
                    if font.size(text)[0]<=limit:return text
                    while text and font.size(text+'…')[0]>limit:text=text[:-1]
                    return text+'…'
                if show_preview:
                    paint_started=time.monotonic_ns()
                    image,boxes=preview.paint(pygame,panel_width,image_height,now,state.get('epoch'),face)
                    paint_ms=(time.monotonic_ns()-paint_started)/1e6
                    surface=pygame.Surface((panel_width,panel_height));surface.fill('#111c24');surface.blit(image,(0,0))
                    if visual['image_valid']:
                        image_id=(preview.frame.meta['fpga_epoch'],preview.frame.serial)
                        if image_id!=last_image_serial:
                            last_image_serial=image_id;draw_count+=1;display_hz=display_rate.update(preview.frame.meta['fpga_epoch'],draw_count,now)
                        frame_text='图像 '+(f'{preview.source_hz:.0f}' if preview.source_hz is not None else '—')+' · 人脸 '+(f'{preview.face_hz:.0f}' if preview.face_hz is not None else '—')+' FPS'
                        pygame.draw.rect(surface,'#111c24',(0,image_height-20,panel_width,20))
                        surface.blit(metric_font.render(fit(frame_text,metric_font,panel_width-12),True,'#d0e1e8'),(6,image_height-18))
                        eyes=[b['pixels'] for b in boxes if b['kind'].startswith('eye')]
                        if eyes:
                            eye_text='眼 '+str(round(min(e[0] for e in eyes)))+'×'+str(round(min(e[1] for e in eyes)))+' px'
                            label_surface=metric_font.render(eye_text,True,'#a7e4e9','#111c24')
                            surface.blit(label_surface,(panel_width-label_surface.get_width()-5,4))
                    else:
                        surface.blit(mini_font.render(preview.error or '图像暂停',True,'#97aab7'),(12,image_height//2-8))
                    surface.blit(mini_font.render(fit(status,mini_font,panel_width-14),True,'#dfedea'),(7,image_height+4))
                    progress=info['progress']
                    if 0<progress<1:pygame.draw.rect(surface,'#83d6cc',(0,panel_height-2,int(panel_width*progress),2))
                    px,py=position(geo['width'],geo['height'],panel_width,panel_height,state)
                    pill.configure(x=geo['x']+px,y=geo['y']+py,stack_mode=X.Above)
                    present_started=time.monotonic_ns()
                    if show_preview:
                        put_surface(pill,gc,surface);pill.map()
                    else:
                        # BASIC already contains the live image; keep its title,
                        # pipeline labels and resource meters unobscured.
                        pill.unmap()
                    svc.measurements.observe(time.monotonic_ns(),read=read_ms,paint=paint_ms,present=(time.monotonic_ns()-present_started)/1e6)
                else:pill.unmap()
                cur=state.get('cursor',{})
                if state.get('target_session',{}).get('phase') in ('SELECTING','LOCKED') and cur.get('xy') and visual['blink']:
                    cursor.change_attributes(background_pixel=0xe3b45a if cur.get('locked') else 0x61ddce)
                    cursor.clear_area();cursor.configure(x=geo['x']+int(cur['xy'][0])-16,y=geo['y']+int(cur['xy'][1])-16,stack_mode=X.Above);cursor.map()
                else:cursor.unmap()
                if card:
                    surface=pygame.Surface((440,460));surface.fill('#181d24')
                    surface.blit(font.render(info['person']+' · '+card['title'],True,'#7cc9d2'),(20,22))
                    for i,row in enumerate(card['rows']):
                        surface.blit(font.render(row,True,'#edf0f3'),(20,85+i*43))
                    # Detailed evaluation guidance remains in the control console.
                    menu.configure(x=geo['x']+(geo['width']-440)//2,y=geo['y']+(geo['height']-460)//2,stack_mode=X.Above)
                    put_surface(menu,mgc,surface);menu.map()
                elif state.get('menu',{}).get('open'):
                    surface=pygame.Surface((440,460));surface.fill('#181d24')
                    for i,label in enumerate(state['menu']['items']):
                        if i==state['menu']['index']:pygame.draw.rect(surface,'#203c43',(8,8+i*42,424,40))
                        surface.blit(font.render(label,True,'#edf0f3'),(20,14+i*42))
                    if state.get('shortcut'):
                        surface.fill('#181d24')
                        surface.blit(font.render('待确认',True,'#edf0f3'),(20,70))
                        surface.blit(font.render(state['shortcut'].get('label','快捷操作'),True,'#7cc9d2'),(20,150))
                        # Interaction help is available in the console, not as an HDMI tutorial.
                        # Interaction help is available in the console, not as an HDMI tutorial.
                    registration=state.get('participants',{}).get('registration')
                    if registration:
                        surface.fill('#181d24')
                        surface.blit(font.render('登记第 '+str(registration['slot'])+' 人',True,'#edf0f3'),(20,20))
                        choices=registration['choices']
                        selected=choices[registration['index']] if choices else None
                        for f in state['participants'].get('faces',[]):
                            rect=f['face_rect'];x=int((rect[0]+rect[2]/2)/640*400)+20
                            chosen=f['track_id']==selected
                            pygame.draw.circle(surface,'#7cc9d2' if chosen else '#8f9da9',(x,170),32,4)
                            pygame.draw.arc(surface,'#7cc9d2' if chosen else '#8f9da9',(x-52,208,104,100),0,3.14159,6)
                            surface.blit(font.render('待确认' if chosen else '候选人',True,'#edf0f3'),(x-30,310))
                        # Interaction help is available in the console, not as an HDMI tutorial.
                    # Interaction help is available in the console, not as an HDMI tutorial.
                    menu.configure(x=geo['x']+(geo['width']-440)//2,y=geo['y']+(geo['height']-460)//2,stack_mode=X.Above)
                    put_surface(menu,mgc,surface);menu.map()
                else:menu.unmap()
                detail=operation_card(state,receipt if now<receipt_until else '')
                if detail!=last_operation:
                    last_operation=detail;surface=pygame.Surface((operation_width,operation_height));surface.fill('#172229')
                    pygame.draw.rect(surface,'#50666e',(0,0,operation_width,operation_height),1)
                    surface.blit(metric_font.render(fit(detail['person'],metric_font,operation_width-28),True,'#94aeb6'),(14,9))
                    surface.blit(font.render(fit(detail['title'],font,operation_width-28),True,'#e2eeeb'),(14,31))
                    words=detail['hint'];lines=['']
                    for letter in words:
                        if mini_font.size(lines[-1]+letter)[0]>operation_width-28:lines.append('')
                        lines[-1]+=letter
                    for i,line in enumerate(lines[:2]):surface.blit(mini_font.render(line,True,'#acc6c4'),(14,62+i*21))
                    if detail['receipt']:surface.blit(metric_font.render(fit(detail['receipt'],metric_font,operation_width-28),True,'#a1dfbd'),(14,105))
                    if 0<detail['progress']<1:pygame.draw.rect(surface,'#83d6cc',(1,operation_height-3,int((operation_width-2)*detail['progress']),2))
                    put_surface(operation,ogc,surface)
                ox,oy=operation_placement(geo['width'],geo['height'],operation_width,operation_height,state)
                operation.configure(x=geo['x']+ox,y=geo['y']+oy,stack_mode=X.Above);operation.map()
                d.flush()
            svc.heartbeat(state.get('epoch',0),preview={'valid':preview.valid(now,state.get('epoch')),
                'source_hz':preview.source_hz,'face_hz':preview.face_hz,'display_hz':display_hz,
                'source_ns':preview.frame.meta['timestamp_ns'] if preview.frame else None,
                'frames_drawn':draw_count,'reads':preview.reads,'reader_resets':preview.replacements,'resize_backend':preview.resize_backend})
    finally:
        preview.close()
        for win in [pill,cursor,menu,operation]:win.destroy()
        d.flush();d.close();sub.close();svc.close();pygame.font.quit()

if __name__=='__main__':main()
