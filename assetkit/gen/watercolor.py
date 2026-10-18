"""Стиль «Акварель»: генератор фонов и деталей.
Фон = акварельные размывы пигмента + коллаж машинописных листков + эскиз тушью по теме утилиты +
сухие мазки кисти + штриховка + брызги и потёки + «капли Поллока» + царапины; светлый (бумага) и тёмный (пигмент на чёрном).

Запуск: python at.py gen watercolor --preset тёмный --apps all
         python at.py parts watercolor --out папка/   # мазок кисти, рваный лист, брызги, бумага
"""
import numpy as np, cv2, math, random
from PIL import Image, ImageDraw, ImageFont
OUT='./'
import os
from ..params import Param, Spec
from ..core import FONTS_DIR, FONTS, draw_text
R=np.random.default_rng(7); random.seed(7)
def vnoise(h,w,cell):
    sh,sw=max(2,h//cell+3),max(2,w//cell+3)
    s=R.random((sh,sw)).astype(np.float32)
    big=cv2.resize(s,(sw*cell,sh*cell),interpolation=cv2.INTER_CUBIC)
    return big[:h,:w]
def fbm(h,w,cell,oct=5,g=.5):
    out=np.zeros((h,w),np.float32); a=1; t=0
    for i in range(oct):
        out+=a*vnoise(h,w,max(2,int(cell/2**i))); t+=a; a*=g
    return out/t
def warp(m,amp,cell):
    h,w=m.shape; dx=(fbm(h,w,cell,4)-.5)*amp; dy=(fbm(h,w,cell,4)-.5)*amp
    X,Y=np.meshgrid(np.arange(w),np.arange(h)); return cv2.remap(m,(X+dx).astype(np.float32),(Y+dy).astype(np.float32),cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
def hexc(s): s=s.lstrip('#'); return np.array([int(s[i:i+2],16)/255 for i in (0,2,4)],np.float32)

def wash(h,w,cx,cy,rx,ry,rough=.55,dark=False):
    Y,X=np.mgrid[0:h,0:w].astype(np.float32)
    d=np.sqrt(((X-cx)/rx)**2+((Y-cy)/ry)**2)
    n=fbm(h,w,int(max(rx,ry)/2.2),5)
    m=np.clip((1.0+rough*(n-.5)*2-d)*3.2,0,1)
    m=warp(m,90,160)
    m=cv2.GaussianBlur(m,(0,0),1.6)
    inner=cv2.GaussianBlur(m,(0,0),9)
    edge=np.clip(m-inner,0,1)*3.2      # пигмент скапливается у края
    gran=fbm(h,w,3,2)                   # грануляция
    bloom=np.clip((fbm(h,w,40,4)-.62)*6,0,1)*m   # затёк «цветной капустой»
    bloom_r=np.clip(cv2.GaussianBlur(bloom,(0,0),3)-bloom,0,1)*4
    dens=(m*(.42+.38*gran)*(1-.55*bloom)+edge*.55+bloom_r*.35) if not dark else (m*(.5+.35*gran)+edge*.6+bloom_r*.5)
    return np.clip(dens,0,1.3)

def splatter(h,w,n,color_mask_list,rmin=1,rmax=14,seed_area=None):
    m=np.zeros((h,w),np.float32)
    for _ in range(n):
        if seed_area: x0,y0,x1,y1=seed_area; cx,cy=R.uniform(x0,x1),R.uniform(y0,y1)
        else: cx,cy=R.uniform(0,w),R.uniform(0,h)
        r=R.uniform(rmin,rmax)**1.0
        cv2.circle(m,(int(cx),int(cy)),int(r),1,-1,cv2.LINE_AA)
        ang=R.uniform(0,2*math.pi); k=int(R.integers(4,22))
        for j in range(k):
            dd=R.uniform(r*.8,r*7); a=ang+R.normal(0,.35)
            rr=max(.6,r*R.uniform(.05,.35)*(1-dd/(r*8)))
            cv2.circle(m,(int(cx+math.cos(a)*dd),int(cy+math.sin(a)*dd)),int(rr),1,-1,cv2.LINE_AA)
        if r>5 and R.random()<.45:  # потёк — только от крупной капли
            L=R.uniform(14,70); x=cx; y=cy; t=max(1.6,r*.7)
            for s in range(int(L)):
                y+=1; x+=R.normal(0,.2); t=max(1.2,t*.992)
                cv2.circle(m,(int(x),int(y)),int(t),1,-1,cv2.LINE_AA)
            cv2.ellipse(m,(int(x),int(y+2)),(max(1,int(t*1.3)),max(2,int(t*2))),0,0,360,1,-1,cv2.LINE_AA)
    return cv2.GaussianBlur(m,(0,0),.7)

def pollock(h,w,n,width=(1,4)):
    m=np.zeros((h,w),np.float32)
    for _ in range(n):
        x,y=R.uniform(-100,w+100),R.uniform(-100,h+100); a=R.uniform(0,2*math.pi); t=R.uniform(*width)
        pts=[]
        for s in range(int(R.uniform(200,900))):
            a+=R.normal(0,.06)+ .02*math.sin(s/30); x+=math.cos(a)*3; y+=math.sin(a)*3
            t=np.clip(t+R.normal(0,.35),.3,width[1]*2.4)
            if R.random()<.012: cv2.circle(m,(int(x),int(y)),int(t*R.uniform(2,4)),1,-1,cv2.LINE_AA)
            if R.random()<.94: cv2.circle(m,(int(x),int(y)),max(0,int(t)),1,-1,cv2.LINE_AA)
    return cv2.GaussianBlur(m,(0,0),.6)

def gesture(h,w,n,wid=(40,120)):
    """широкий мазок сухой кистью: короткий, с ускоряющимся изгибом; тело + рваные щетинки"""
    m=np.zeros((h,w),np.float32)
    for _ in range(n):
        x,y=R.uniform(0,1)*w,R.uniform(0,1)*h; a=R.uniform(0,2*math.pi); W_=R.uniform(*wid); L=int(R.uniform(140,420))
        bend=R.normal(0,.004)
        nb=int(W_/1.6); offs=np.sort(R.uniform(-W_/2,W_/2,nb)); press=R.uniform(.35,1,nb); stop=R.uniform(.55,1,nb)*L
        for s in range(L):
            bend=bend*.96+R.normal(0,.0016); a+=bend; x+=math.cos(a)*2.2; y+=math.sin(a)*2.2
            fade=min(1,s/18)*(1-max(0,(s-L*.6)/(L*.4)))**.6
            nx,ny=-math.sin(a),math.cos(a)
            for o,pz,st in zip(offs,press,stop):
                if s>st or R.random()<.08+(1-fade)*.5: continue
                cv2.circle(m,(int(x+nx*o),int(y+ny*o)),2,pz*fade,-1)
    m=cv2.GaussianBlur(m,(0,0),1.2)
    return np.clip(m*(0.7+0.6*fbm(h,w,6,3)),0,1)

def hatch(h,w,groups):
    m=np.zeros((h,w),np.float32)
    for _ in range(groups):
        cx,cy=R.uniform(0,w),R.uniform(0,h); a=R.uniform(-1.2,-.4); L=R.uniform(18,46); k=int(R.integers(8,26))
        for i in range(k):
            ox,oy=cx+i*R.uniform(3,6),cy+R.normal(0,4)
            cv2.line(m,(int(ox),int(oy)),(int(ox+math.cos(a)*L),int(oy+math.sin(a)*L)),R.uniform(.4,.9),1,cv2.LINE_AA)
    return m

def scratches(h,w,n):
    m=np.zeros((h,w),np.float32)
    for _ in range(n):
        x,y=R.uniform(0,w),R.uniform(0,h); a=R.normal(-.35,.5); L=R.uniform(80,600)
        cv2.line(m,(int(x),int(y)),(int(x+math.cos(a)*L),int(y+math.sin(a)*L)),R.uniform(.3,1),1,cv2.LINE_AA)
    return m

import os
FONT_M=os.path.join(FONTS_DIR, FONTS['typewriter'])
WORDS=['ДЕЛО № 41/2','МАРТИНЕЙЗ','ВАРИАНТ','ПРОТОКОЛ ОСМОТРА','НЕ ВЫНОСИТЬ','СВИДЕТЕЛЬ','ω = 2πn/60','Mс = 250 Н·м','кг·м²','J = Jдв + Jн/i²','ЛОГИКА','ЭНЦИКЛОПЕДИЯ','ЛИСТ 3','ПОДПИСЬ ___________','29.10','ОТЧЁТ','Tм ≥ 4Tэ','СЕКРЕТНО']
def collage(h,w,n,light=True):
    """рваные листки: машинопись, линовка, штамп"""
    layer=np.zeros((h,w,4),np.float32)
    for i in range(n):
        pw,ph=int(R.uniform(160,420)),int(R.uniform(110,300))
        card=Image.new('RGBA',(pw,ph),(0,0,0,0)); dr=ImageDraw.Draw(card)
        base=(236,229,214) if light else (52,48,42)
        if R.random()<.35: base=(214,224,226) if light else (38,46,50)
        dr.rectangle([0,0,pw,ph],fill=base+(255,))
        ink=(40,36,32) if light else (210,200,182)
        if R.random()<.5:
            for yy in range(18,ph,16): dr.line([(0,yy),(pw,yy)],fill=(120,150,170,90) if light else (120,140,150,70),width=1)
        fs=int(R.uniform(11,16))
        yy=int(R.uniform(8,20))
        while yy<ph-14:
            s=random.choice(WORDS)
            draw_text(dr,(int(R.uniform(6,20)),yy),s,'typewriter',fs,ink+(int(R.uniform(120,210)),)); yy+=int(R.uniform(16,26))
        if R.random()<.4:
            cx,cy=int(R.uniform(40,pw-40)),int(R.uniform(40,ph-40)); rr=int(R.uniform(22,36))
            col=(150,40,40,140) if light else (190,90,70,120)
            dr.ellipse([cx-rr,cy-rr,cx+rr,cy+rr],outline=col,width=3); dr.ellipse([cx-rr+6,cy-rr+6,cx+rr-6,cy+rr-6],outline=col,width=1)
        a=np.asarray(card).astype(np.float32)/255
        # рваный край
        hh,ww=a.shape[:2]; Y,X=np.mgrid[0:hh,0:ww]; ed=np.minimum(np.minimum(X,ww-1-X),np.minimum(Y,hh-1-Y)).astype(np.float32)
        nn=fbm(hh,ww,14,4); alpha=np.clip((ed-8*nn-2)/2,0,1)
        a[...,3]*=alpha
        # фото-копийный шум и пятна
        a[...,:3]*= (0.9+0.1*fbm(hh,ww,2,2))[...,None]
        img=Image.fromarray((a*255).astype(np.uint8)).rotate(R.uniform(-14,14),expand=True,resample=Image.BICUBIC)
        b=np.asarray(img).astype(np.float32)/255
        x0,y0=int(R.uniform(-80,w-80)),int(R.uniform(-60,h-60))
        bh,bw=b.shape[:2]; xs,ys=max(0,x0),max(0,y0); xe,ye=min(w,x0+bw),min(h,y0+bh)
        if xe<=xs or ye<=ys: continue
        sub=b[ys-y0:ye-y0, xs-x0:xe-x0]; al=sub[...,3:4]*R.uniform(.5,.85)
        layer[ys:ye,xs:xe,:3]=layer[ys:ye,xs:xe,:3]*(1-al)+sub[...,:3]*al
        layer[ys:ye,xs:xe,3:4]=np.maximum(layer[ys:ye,xs:xe,3:4],al)
    return layer

def ring(h,w,cx,cy,r):
    Y,X=np.mgrid[0:h,0:w].astype(np.float32); d=np.sqrt((X-cx)**2+(Y-cy)**2)
    n=fbm(h,w,20,3); rr=r*(1+.06*(n-.5))
    return np.clip(1-np.abs(d-rr)/3.5,0,1)*.8+np.clip(1-d/rr,0,1)*.08


# ---------- сюжеты утилит: эскизы тушью «от руки» ----------
def jl(m,pts,th=1.4,rep=2,jit=1.6):
    pts=np.array(pts,np.float32)
    for r in range(rep):
        q=pts+R.normal(0,jit,pts.shape)
        q=np.vstack([q[0]]+[q[i-1]*.5+q[i]*.5+R.normal(0,jit*.4,2) for i in range(1,len(q))]+[q[-1]]) if len(q)>2 else q
        cv2.polylines(m,[q.astype(np.int32).reshape(-1,1,2)],False,R.uniform(.6,1),max(2,int(th*2.1+R.normal(0,.5))),cv2.LINE_AA)
def jcircle(m,c,r,th=1.4,rep=2,n=90):
    for k in range(rep):
        a0=R.uniform(0,6.28); pts=[(c[0]+(r+R.normal(0,1.5))*math.cos(a0+i*6.6/n),c[1]+(r+R.normal(0,1.5))*math.sin(a0+i*6.6/n)) for i in range(n)]
        jl(m,pts,th,1,.8)
def curve(m,x0,y0,w,h,f,th=1.6,n=120):
    jl(m,[(x0+w*i/n,y0-h*f(i/n)) for i in range(n+1)],th,2,1.2)
def axes(m,x0,y0,w,h):
    jl(m,[(x0,y0-h),(x0,y0),(x0+w,y0)],1.4,2,1.2); jl(m,[(x0-5,y0-h+10),(x0,y0-h),(x0+5,y0-h+10)],1.2,1,.6); jl(m,[(x0+w-10,y0-5),(x0+w,y0),(x0+w-10,y0+5)],1.2,1,.6)
def gear(m,c,r,z,th=1.6):
    pts=[]
    for i in range(z*4+1):
        a=i*2*math.pi/(z*4); rr=r if (i%4) in (0,1) else r*.86
        pts.append((c[0]+rr*math.cos(a),c[1]+rr*math.sin(a)))
    jl(m,pts,th,2,1.0); jcircle(m,c,r*.25,th); jcircle(m,c,r*.62,1.0,1)
def sketch(h,w,app):
    m=np.zeros((h,w),np.float32); S=min(h,w)/1200
    def P(x,y): return (x*w,y*h)
    if app=='sapr-labs':
        c=P(.78,.3); jcircle(m,c,190*S,2); jcircle(m,c,120*S,1.6)
        for k in range(12): a=k*math.pi/6; jl(m,[(c[0]+130*S*math.cos(a),c[1]+130*S*math.sin(a)),(c[0]+182*S*math.cos(a),c[1]+182*S*math.sin(a))],1.4,1)
        jl(m,[(c[0]-30*S,c[1]),(c[0]+30*S,c[1])],2); jl(m,[(c[0],c[1]-30*S),(c[0],c[1]+30*S)],2)
        x0,y0=.08*w,.78*h; axes(m,x0,y0,420*S,240*S); curve(m,x0,y0,400*S,200*S,lambda u:1-math.exp(-u*7)*math.cos(u*22)*.9 if u>0 else 0)
        x1,y1=.42*w,.95*h; axes(m,x1,y1,380*S,200*S); jl(m,[(x1+10*S,y1-180*S),(x1+150*S,y1-120*S),(x1+380*S,y1-20*S)],2.2)
        for i,(bx,by) in enumerate([(.1,.18),(.24,.18),(.38,.18)]):
            jl(m,[(bx*w,by*h),(bx*w+110*S,by*h),(bx*w+110*S,by*h+60*S),(bx*w,by*h+60*S),(bx*w,by*h)],1.6)
            if i<2: jl(m,[(bx*w+110*S,by*h+30*S),((bx+.14)*w,by*h+30*S)],1.4)
    elif app=='krrs-robot':
        cx,cy=.74*w,.62*h; jcircle(m,(cx-70*S,cy),56*S,2.2); jcircle(m,(cx+70*S,cy),56*S,2.2)
        body=[(cx-60*S,cy-30*S),(cx-40*S,cy-300*S),(cx+60*S,cy-310*S),(cx+60*S,cy-20*S)]; jl(m,body+[body[0]],2)
        jl(m,[(cx,cy-310*S),(cx,cy-430*S)],1,1); 
        jl(m,[(cx+40*S*math.sin(a),cy-420*S+40*S*math.cos(a)) for a in np.linspace(-.1,.6,20)],1.2)
        x0,y0=.08*w,.82*h; axes(m,x0,y0,460*S,260*S); curve(m,x0,y0-120*S,440*S,120*S,lambda u:math.exp(-u*4)*math.cos(u*26))
        for bx in (.1,.28):
            x=bx*w; y=.12*h; jl(m,[(x+12*S,y),(x,y),(x,y+170*S),(x+12*S,y+170*S)],2); jl(m,[(x+200*S,y),(x+212*S,y),(x+212*S,y+170*S),(x+200*S,y+170*S)],2)
    elif app=='op-coursework':
        gear(m,P(.76,.32),170*S,22); gear(m,(P(.76,.32)[0]-280*S,P(.76,.32)[1]+150*S),110*S,14)
        x0,y0=.1*w,.78*h; L=560*S
        jl(m,[(x0,y0-40*S),(x0+L,y0-40*S),(x0+L,y0+40*S),(x0,y0+40*S),(x0,y0-40*S)],2)
        for k in range(26): jl(m,[(x0+k*L/26,y0+40*S),(x0+(k+1)*L/26,y0-40*S)],1,1,.6)
        jl(m,[(x0,y0+90*S),(x0+L,y0+90*S)],1,1); jl(m,[(x0+10,y0+84*S),(x0,y0+90*S),(x0+10,y0+96*S)],1,1); jl(m,[(x0+L-10,y0+84*S),(x0+L,y0+90*S),(x0+L-10,y0+96*S)],1,1)
        hx,hy=.12*w,.2*h
        jl(m,[(hx+i*4*S,hy+70*S*math.sin(i/7)) for i in range(140)],1.8)
    elif app=='eco-pdv':
        bx,by=.72*w,.92*h; jl(m,[(bx,by),(bx+20*S,by-420*S),(bx+70*S,by-420*S),(bx+90*S,by)],2.2)
        for k in range(4): jl(m,[(bx+15*S+k*3,by-330*S+k*40*S),(bx+75*S-k*3,by-330*S+k*40*S)],1,1)
        sx,sy=bx+45*S,by-430*S
        for k in range(5):
            pts=[(sx-i*9*S,sy-i*1.8*S-60*S*math.sin(i/9+k)*(i/60)-k*14*S) for i in range(70)]; jl(m,pts,1.5,1,1.4)
        x0,y0=.08*w,.82*h; axes(m,x0,y0,520*S,260*S); curve(m,x0,y0,500*S,220*S,lambda u:(u*4.5)*math.exp(1-u*4.5))
        for cx,cy,rr in [(.2,.16,60),(.3,.12,80),(.42,.18,55)]: jcircle(m,(cx*w,cy*h),rr*S,1.4,1)
        for k in range(4): y=.33*h+k*26*S; jl(m,[(.08*w,y),(.08*w+160*S,y-6*S)],1.2,1); jl(m,[(.08*w+150*S,y-12*S),(.08*w+160*S,y-6*S),(.08*w+148*S,y+2*S)],1.2,1)
    return cv2.GaussianBlur(m,(0,0),.6)
APPW={'sapr-labs':['ЛАЧХ','ω = 2πn/60','Mс = 250 Н·м','Tм ≥ 4Tэ','ПИД-РЕГУЛЯТОР','2ПБ90МУХЛ4','W(p) = k/(Tp+1)','ТАХОГЕНЕРАТОР','ЛР № 3','ОПТИМУМ ПО МОДУЛЮ'],
      'krrs-robot':['LQR','K = [−0,71 −39,5]','θ, ψ, φ','ẋ = Ax + Bu','ШИМ 10 бит','λmax = 5,735','ЭТАП 4','Q = diag(…)','ГИРОСКОП','ЭНКОДЕР'],
      'op-coursework':['z₁/z₂ = 25/56','aw = 160 мм','σH ≤ [σ]H','ГОСТ 2.104','ВАЛ ВЕДОМЫЙ','ШПОНКА 10×8','МУФТА МУВП','КОМПАС-3D','ЧЕРВЯК q = 8','ПОДШИПНИК 7308'],
      'eco-pdv':['ПДВ','Cmax = 0,197 мг/м³','ПДК м.р.','Xmax = 171 м','H = 30 м','CO · NO₂ · SO₂','ВЕТЕР 1 м/с','ЗАДАЧА 1.1','ФОН','ЭФФЕКТ СУММАЦИИ']}
APPHUE={'sapr-labs':'#3d6f9e','krrs-robot':'#6b5096','op-coursework':'#2f7a70','eco-pdv':'#6e8a2c'}

PALETTES={
 'бумага': dict(dark=False, ground='#e8e1d2', ink='#1f1b17', hatch='#2a2622', ring='#9a6b3a', scratch=(.2,.18,.16),
     washes=[('#7f9fa3',.18,.22,.36,.28),('#c99a4e',.82,.12,.33,.22),('#b0583a',.88,.78,.3,.3),('#56668a',.15,.85,.4,.25),('#8a7da0',.52,.55,.22,.2),('#a5a77a',.5,.05,.25,.14),('#c8b98c',.35,.45,.3,.25)],
     glazes=[('#3d5b6b',.3,.3,.25,.2),('#9c4a2c',.7,.65,.22,.18)],
     splat=[('#1d1a17',18,12),('#8b2f1f',7,9),('#2d4f5c',8,8)], gest=[('#3b3f4a',3,.42),('#7a3a24',2,.4),('#2f4f57',2,.36),('#1e1b18',2,.38)]),
 'грунт': dict(dark=True, ground='#141311', ink='#ddd3ba', hatch='#d6ccb4', ring='#c9a36a', scratch=(.85,.82,.75),
     washes=[('#2f5a63',.15,.2,.38,.3),('#8d6a2e',.85,.1,.3,.22),('#7a2c1d',.9,.82,.32,.3),('#2a3d66',.12,.88,.42,.26),('#5a3f6e',.55,.5,.25,.2),('#46623f',.48,.04,.25,.12)],
     glazes=[], splat=[('#d9cfb8',12,9),('#b9502f',7,9),('#6aa3b0',7,7)], gest=[('#cfc3a6',2,.26),('#b5552f',2,.36),('#4f8a96',2,.32),('#e6dcc4',1,.2)]),
 'сепия': dict(dark=False, ground='#eadcc0', ink='#2b1d12', hatch='#3a2a1c', ring='#8a5a2a', scratch=(.25,.18,.12),
     washes=[('#a27a4a',.2,.25,.36,.28),('#c99a4e',.8,.15,.33,.22),('#7a4a2a',.85,.8,.3,.3),('#6a5a48',.15,.85,.4,.25),('#b08a5a',.5,.5,.25,.2)],
     glazes=[('#5a3a22',.3,.3,.25,.2),('#8b4a26',.7,.65,.22,.18)],
     splat=[('#20140c',18,12),('#6b2f15',7,9)], gest=[('#3b2a1a',3,.42),('#7a4a24',2,.4)]),
 'индиго': dict(dark=True, ground='#0e1220', ink='#d6deef', hatch='#c4cee6', ring='#7c8fc2', scratch=(.8,.85,.95),
     washes=[('#2a3f7a',.15,.2,.38,.3),('#4a2f6e',.85,.1,.3,.22),('#1f5a6e',.9,.82,.32,.3),('#5a6a9a',.12,.88,.42,.26),('#7a3a5a',.55,.5,.25,.2)],
     glazes=[], splat=[('#e0e6f2',12,9),('#c46a8a',7,9),('#6ab0c8',7,7)], gest=[('#aab8d8',2,.26),('#8a4a7a',2,.36),('#4f8aa6',2,.32)]),
}
APPS=list(APPW)
SPEC=Spec('watercolor',[
    Param('app','sapr-labs',kind='choice',choices=APPS+['нет'],group='сюжет',help='эскиз тушью и слова коллажа; «нет» — без эскиза',rand=False),
    Param('palette','бумага',kind='choice',choices=list(PALETTES),group='сюжет',help='грунт и пигменты: бумага/сепия — светлые, грунт/индиго — тёмные'),
    Param('width',1920,320,4096,group='сюжет',help='ширина, px',rand=False), Param('height',1200,240,4096,group='сюжет',help='высота, px',rand=False),
    Param('hue','авто',group='сюжет',help='главный пигмент: цвет #rrggbb или «авто» — цвет утилиты'),
    Param('washes',1.0,0.0,2.0,group='пигмент',help='плотность размывов',rand=(.5,1.6)), Param('wash_size',1.0,.4,2.0,group='пигмент',help='размер размывов',rand=(.6,1.5)),
    Param('wash_count',7,0,14,group='пигмент',help='сколько размывов взять из палитры (по кругу)'),
    Param('scatter',0.0,0.0,1.0,group='пигмент',help='разброс положения размывов (0 — как в палитре)'),
    Param('glazes',1.0,0.0,2.0,group='пигмент',help='прозрачные лессировки поверх коллажа'),
    Param('collage',9,0,24,group='коллаж',help='число листков',rand=(0,16)), Param('collage_opacity',1.0,0.0,1.6,group='коллаж',help='заметность листков'),
    Param('words','авто',group='коллаж',help='слова листков через «|»; «авто» — из утилиты'),
    Param('sketch',1.0,0.0,1.3,group='тушь',help='эскиз тушью',rand=(.4,1.2)), Param('splatter',1.0,0.0,3.0,group='тушь',help='брызги'),
    Param('splatter_size',1.0,.3,3.0,group='тушь',help='размер брызг',rand=(.5,2)), Param('gestures',1.0,0.0,3.0,group='тушь',help='сухие мазки кисти'),
    Param('hatch',17,0,60,group='тушь',help='группы штриховки',rand=(0,35)), Param('pollock',5,0,30,group='тушь',help='нити Поллока',rand=(0,14)),
    Param('scratches',65,0,300,group='фактура',help='царапины',rand=(0,150)), Param('rings',2,0,8,group='фактура',help='кольца от кружки (на светлом)'),
    Param('paper',1.0,0.0,3.0,group='фактура',help='зерно бумаги'), Param('vignette',1.0,0.0,2.5,group='фактура',help='виньетка'),
],{
    'светлый': {}, 'тёмный': dict(palette='грунт'),
    'лёгкий набросок': dict(washes=.55, collage=3, splatter=.4, gestures=.4, hatch=6, pollock=1, scratches=20, glazes=.4),
    'экспрессия': dict(washes=1.5, wash_size=1.3, splatter=2.4, splatter_size=1.8, gestures=2.4, pollock=16, hatch=30, collage=5),
    'досье': dict(palette='сепия', collage=18, collage_opacity=1.3, washes=.7, pollock=2, rings=4),
    'ночная тушь': dict(palette='индиго', splatter=1.6, pollock=9, collage=4),
    'чистый размыв': dict(collage=0, sketch=0, splatter=0, gestures=0, hatch=0, pollock=0, scratches=0, rings=0, washes=1.3),
},title='Акварель: фон',about='Акварельный экспрессионизм: размывы, коллаж листков, эскиз тушью, брызги, Поллок, штриховка')

def background(P, seed=7):
    global WORDS, R
    R=np.random.default_rng(seed); random.seed(seed)
    W,H=int(P['width']),int(P['height']); pal=PALETTES[P['palette']]; dark=pal['dark']; app=P['app']
    if P['words']=='авто': WORDS=APPW.get(app,[])+['ДЕЛО № 41/2','ПРОТОКОЛ','ЛИСТ 3','ПОДПИСЬ ________','НЕ ВЫНОСИТЬ']
    else: WORDS=[w.strip() for w in str(P['words']).split('|') if w.strip()] or [' ']
    hue=P['hue'] if str(P['hue']).startswith('#') else APPHUE.get(app,'#5a6a8a')
    img=np.ones((H,W,3),np.float32)*hexc(pal['ground'])
    pp=fbm(H,W,3,3); img*=(1+((.3*pp-.15) if dark else (.07*pp-.07))*P['paper'])[...,None]
    def put(col,cx,cy,rx,ry,k):
        sc=P['scatter']; cx=cx+R.uniform(-.4,.4)*sc; cy=cy+R.uniform(-.4,.4)*sc; s=P['wash_size']
        d=np.clip(wash(H,W,cx*W,cy*H,rx*W*s,ry*H*s,dark=dark)*k,0,1)
        return d
    ws=pal['washes']; n=int(P['wash_count'])
    for i in range(n):
        col,cx,cy,rx,ry=ws[i%len(ws)]
        if i>=len(ws): cx,cy=R.uniform(0,1),R.uniform(0,1)
        d=put(col,cx,cy,rx,ry,R.uniform(.55,.9)*P['washes']); c=hexc(col)
        img=1-(1-img)*(1-d[...,None]*c*1.15) if dark else img*((1-d[...,None]*.85)+d[...,None]*.85*c)
    if P['washes']>0:
        d=put(hue,.6,.4,.32,.26,.8*min(1.3,P['washes']))
        img=1-(1-img)*(1-d[...,None]*hexc(hue)*1.2) if dark else img*((1-d[...,None]*.85)+d[...,None]*.85*hexc(hue))
    if P['collage']>0 and P['collage_opacity']>0:
        cl=collage(H,W,int(P['collage']),not dark); a=np.clip(cl[...,3:4]*(.42 if dark else .55)*P['collage_opacity'],0,1); img=img*(1-a)+cl[...,:3]*a
    if app!='нет' and P['sketch']>0:
        sk=np.clip(sketch(H,W,app)*(.7 if dark else .78)*P['sketch'],0,1); img=img*(1-sk[...,None])+hexc(pal['ink'])*sk[...,None]
    for col,cx,cy,rx,ry in pal['glazes']:
        if P['glazes']<=0: break
        d=put(col,cx,cy,rx,ry,.45*P['glazes']); img*=(1-d[...,None]*.7)+d[...,None]*.7*hexc(col)
    so=.75 if dark else .9
    for col,nn,rm in pal['splat']:
        k=int(round(nn*P['splatter']))
        if k<=0: continue
        m=splatter(H,W,k,None,1,max(2,rm*P['splatter_size'])); img=img*(1-m[...,None]*so)+hexc(col)*m[...,None]*so
    for col,nn,o in pal['gest']:
        k=int(round(nn*P['gestures']))
        if k<=0: continue
        gg=gesture(H,W,k); img=img*(1-gg[...,None]*o)+hexc(col)*gg[...,None]*o
    ho=.35 if dark else .5
    if P['hatch']>0: hh=hatch(H,W,int(P['hatch'])); img=img*(1-hh[...,None]*ho)+hexc(pal['hatch'])*hh[...,None]*ho
    po=.65 if dark else .8
    if P['pollock']>0: p=pollock(H,W,int(P['pollock']),(.8,2.4)); img=img*(1-p[...,None]*po)+hexc(pal['ink'])*p[...,None]*po
    so=.25 if dark else .35
    if P['scratches']>0: sc=scratches(H,W,int(P['scratches'])); img=img*(1-sc[...,None]*so)+np.array(pal['scratch'])*sc[...,None]*so
    if not dark:
        for _ in range(int(P['rings'])):
            rg=ring(H,W,R.uniform(.1,.9)*W,R.uniform(.1,.9)*H,R.uniform(60,110)); img*=(1-rg[...,None]*.25)+rg[...,None]*.25*hexc(pal['ring'])
    Y,X=np.mgrid[0:H,0:W]; v=np.clip(1-(.45 if dark else .18)*P['vignette']*(((X/W-.5)**2+(Y/H-.5)**2)*2.2),0,1); img*=v[...,None]
    return np.clip(img,0,1)

def brush(W=900,H=90):
    """сухая кисть: щетинки, рваные концы, пропуски"""
    m=np.zeros((H,W),np.float32)
    for b in range(70):
        y0=R.uniform(18,H-18); wv=R.uniform(.6,2.2); amp=R.uniform(2,6); ph=R.uniform(0,6)
        x_start=R.uniform(0,60); x_end=W-R.uniform(0,110)
        for x in np.arange(x_start,x_end,1.0):
            if R.random()<.06+.5*max(0,(x-x_end+160)/160): continue
            y=y0+amp*math.sin(x/170+ph)+ (x-x_start)*R.uniform(-.004,.004)
            t=wv*(1-max(0,(x_start+30-x)/30))
            cv2.circle(m,(int(x),int(y)),max(0,int(t)),R.uniform(.5,1),-1,cv2.LINE_AA)
    m=cv2.GaussianBlur(m,(0,0),.8)
    m=np.clip(m*(0.65+0.5*fbm(H,W,8,3)),0,1)
    a=(m*255).astype(np.uint8); rgba=np.dstack([np.full_like(a,255)]*3+[a])
    Image.fromarray(rgba,'RGBA').save(OUT+'de-brush.png',optimize=True)

def card(theme,S=520):
    """лист бумаги с рваным краем — для border-image (9 частей)"""
    light=theme=='light'
    base=hexc('#ece3cf') if light else hexc('#1b1916')
    img=np.ones((S,S,3),np.float32)*base
    g=fbm(S,S,3,3); img*= (0.94+0.1*g)[...,None] if light else (0.8+0.4*g)[...,None]
    d=wash(S,S,S*.75,S*.2,S*.5,S*.3)*.25; img*= (1-d[...,None]*.6)+d[...,None]*.6*(hexc('#b89b6a') if light else hexc('#3a4a4f'))
    Y,X=np.mgrid[0:S,0:S]; ed=np.minimum(np.minimum(X,S-1-X),np.minimum(Y,S-1-Y)).astype(np.float32)
    nn=fbm(S,S,10,5); alpha=np.clip((ed-16*nn-6)/1.6,0,1)
    darken=np.clip(1-(ed-16*nn-6)/22,0,1)*(0.25 if light else 0.5)   # подгоревший/затёртый край
    img*= (1-darken)[...,None]
    fib=np.clip((ed-16*nn-6)/1.6+1,0,1)-alpha    # волокна на разрыве
    img=img*(1-fib[...,None]*.6)+ (np.array([1,1,1]) if light else np.array([.35,.33,.3]))*fib[...,None]*.6
    alpha=np.maximum(alpha,fib*.6)
    rgba=np.dstack([np.clip(img,0,1),alpha]); Image.fromarray((rgba*255).astype(np.uint8),'RGBA').save(OUT+f'de-card-{theme}.png',optimize=True)

def splat_corner(theme,S=420):
    m=splatter(S,S,9,None,2,16,(S*.55,S*.0,S*.95,S*.35))+pollock(S,S,2,(1,2))*.8
    m=np.clip(m,0,1); col=(26,24,21) if theme=='light' else (215,205,185)
    a=(m*235).astype(np.uint8); rgba=np.dstack([np.full_like(a,col[0]),np.full_like(a,col[1]),np.full_like(a,col[2]),a])
    Image.fromarray(rgba,'RGBA').save(OUT+f'de-splat-{theme}.png',optimize=True)



def wrap_blur(x,sx,sy=None):
    """гауссово размытие с периодическими краями (через FFT) — для бесшовных плиток"""
    sy=sx if sy is None else sy; h,w=x.shape
    fy=np.fft.fftfreq(h)[:,None]; fx=np.fft.fftfreq(w)[None,:]
    k=np.exp(-2*(math.pi**2)*((fx*sx)**2+(fy*sy)**2))
    return np.real(np.fft.ifft2(np.fft.fft2(x)*k)).astype(np.float32)
def paper_tile(theme,S=384):
    """бесшовная бумага: зерно, волокна, мягкие пятна"""
    light=theme=='light'
    n=R.random((S,S)).astype(np.float32)
    a=wrap_blur(n,.8); b=wrap_blur(n,14); fib=wrap_blur(R.random((S,S)).astype(np.float32),4,.6)
    v=(a-a.mean())*.55+(b-b.mean())*7+(fib-fib.mean())*.8
    base=hexc('#efe6d2') if light else hexc('#1a1814')
    img=base*(1+v[...,None]*(.16 if light else .55))
    Image.fromarray((np.clip(img,0,1)*255).astype(np.uint8)).save(OUT+f'de-paper-{theme}.webp',quality=86,method=6)

apply = background

def parts(out_dir, seed=7, themes=('light', 'dark')):
    """мазок кисти, рваный лист (border-image), брызги в угол, бесшовная бумага — набор деталей стиля «Акварель»"""
    global OUT, R
    OUT = out_dir.rstrip('/\\') + '/'; os.makedirs(OUT, exist_ok=True); R = np.random.default_rng(seed); random.seed(seed)
    brush(); [card(t) for t in themes]; [splat_corner(t) for t in themes]; [paper_tile(t) for t in themes]
    return OUT
