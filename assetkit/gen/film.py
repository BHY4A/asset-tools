"""Стиль «Засветка»: кадры выжженной плёнки (день) и бирюзово-янтарной ночи.
Небо с дымкой, дальний город, силуэт-сюжет утилиты (ЛЭП / робот / балка с грузом и шестерни / трубы с дымом),
боке, засветка края, слова-реплики, двоящиеся поверх кадра, двойная экспозиция, кросс-процесс,
хроматическая аберрация, врезки сплит-экрана, зерно.

Запуск: python at.py gen film --preset ночь --apps all
"""
import numpy as np, cv2, math, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter
R=np.random.default_rng(3)
import os
from ..params import Param, Spec
from ..core import FONTS_DIR, FONTS, draw_text
FB=os.path.join(FONTS_DIR, FONTS['cond'])
def hexc(s): s=s.lstrip('#'); return np.array([int(s[i:i+2],16)/255 for i in (0,2,4)],np.float32)

def skyline(m,W,H,base,seed):
    r=np.random.default_rng(seed); x=-20
    while x<W:
        bw=r.uniform(40,130); bh=r.uniform(.08,.42)*H
        cv2.rectangle(m,(int(x),int(base-bh)),(int(x+bw),int(base)),1,-1)
        if r.random()<.5:  # окна
            pass
        if r.random()<.25: cv2.line(m,(int(x+bw/2),int(base-bh)),(int(x+bw/2),int(base-bh-r.uniform(20,60))),1,2)
        x+=bw+r.uniform(-10,12)
def pylon(m,x,base,h,s=1):
    pts=[(x-40*s,base),(x-8*s,base-h),(x+8*s,base-h),(x+40*s,base)]
    cv2.polylines(m,[np.array(pts,np.int32)],False,1,max(1,int(4*s)),cv2.LINE_AA)
    for k in range(6):
        y=base-h*k/6; y2=base-h*(k+1)/6; xl=x-40*s+32*s*k/6; xr=x+40*s-32*s*k/6; xl2=x-40*s+32*s*(k+1)/6; xr2=x+40*s-32*s*(k+1)/6
        cv2.line(m,(int(xl),int(y)),(int(xr2),int(y2)),1,max(1,int(2*s)),cv2.LINE_AA); cv2.line(m,(int(xr),int(y)),(int(xl2),int(y2)),1,max(1,int(2*s)),cv2.LINE_AA)
    for k,(arm,yy) in enumerate([(70,.82),(55,.68)]):
        cv2.line(m,(int(x-arm*s),int(base-h*yy)),(int(x+arm*s),int(base-h*yy)),1,max(1,int(4*s)),cv2.LINE_AA)
    return [(x-70*s,base-h*.82),(x+70*s,base-h*.82),(x-55*s,base-h*.68),(x+55*s,base-h*.68)]
def wire(m,a,b,sag):
    pts=[(a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t+sag*4*t*(1-t)) for t in np.linspace(0,1,60)]
    cv2.polylines(m,[np.array(pts,np.int32)],False,1,2,cv2.LINE_AA)
def gear(m,c,r,z):
    pts=[]
    for i in range(z*4):
        a=i*2*math.pi/(z*4); rr=r if (i%4) in (0,1) else r*.85; pts.append((c[0]+rr*math.cos(a),c[1]+rr*math.sin(a)))
    cv2.fillPoly(m,[np.array(pts,np.int32)],1,cv2.LINE_AA); cv2.circle(m,(int(c[0]),int(c[1])),int(r*.3),0,-1,cv2.LINE_AA)

def motifs(m,app,W,H,base):
    u=W/1920
    if app=='sapr-labs':
        a=pylon(m,.62*W,base,.62*H,1.9*u); b=pylon(m,.95*W,base+30*u,.5*H,1.5*u); c=pylon(m,.28*W,base+10*u,.42*H,1.2*u)
        for i in range(4): wire(m,a[i],b[i],60); wire(m,c[i%4],a[i],80)
    elif app=='krrs-robot':
        cx=.66*W; s=2.6*u
        cv2.circle(m,(int(cx-60*s),int(base-38*s)),int(38*s),1,-1,cv2.LINE_AA); cv2.circle(m,(int(cx+60*s),int(base-38*s)),int(38*s),1,-1,cv2.LINE_AA)
        body=np.array([(cx-46*s,base-50*s),(cx-20*s,base-300*s),(cx+36*s,base-304*s),(cx+46*s,base-46*s)],np.int32); cv2.fillPoly(m,[body],1,cv2.LINE_AA)
        cv2.rectangle(m,(int(cx-24*s),int(base-340*s)),(int(cx+40*s),int(base-300*s)),1,-1); cv2.circle(m,(int(cx+8*s),int(base-320*s)),int(10*s),0,-1,cv2.LINE_AA)
        cv2.line(m,(int(cx-60*s),int(base-38*s)),(int(cx+60*s),int(base-38*s)),1,max(1,int(8*s)))
        cv2.line(m,(int(cx+10*s),int(base-335*s)),(int(cx+20*s),int(base-420*s)),1,max(1,int(3*s)),cv2.LINE_AA)
    elif app=='op-coursework':
        x0=.5*W; top=base-.6*H
        for xx in (x0,x0+.36*W): cv2.rectangle(m,(int(xx),int(top)),(int(xx+26),int(base)),1,-1)
        cv2.rectangle(m,(int(x0-60),int(top)),(int(x0+.36*W+90),int(top+40)),1,-1)
        for k in range(18): cv2.line(m,(int(x0-60+k*44),int(top)),(int(x0-38+k*44),int(top+40)),0,3)
        cv2.line(m,(int(x0+.2*W),int(top+40)),(int(x0+.2*W),int(top+.3*H)),1,3); cv2.rectangle(m,(int(x0+.2*W-40),int(top+.3*H)),(int(x0+.2*W+40),int(top+.3*H+50)),1,-1)
        gear(m,(.2*W,base-.34*H),.16*H,20); gear(m,(.2*W+.24*H,base-.2*H),.1*H,13)
    elif app=='eco-pdv':
        for i,(xx,hh,ww) in enumerate([(.55,.62,.04),(.64,.72,.05),(.76,.55,.035)]):
            x=xx*W; cv2.fillPoly(m,[np.array([(x-ww*W*.6,base),(x-ww*W*.4,base-hh*H),(x+ww*W*.4,base-hh*H),(x+ww*W*.6,base)],np.int32)],1,cv2.LINE_AA)
        cv2.rectangle(m,(int(.48*W),int(base-.18*H)),(int(.86*W),int(base)),1,-1)
def smoke(W,H,app,base):
    sm=np.zeros((H,W),np.float32)
    if app!='eco-pdv': return sm
    for xx,hh in [(.55,.62),(.64,.72),(.76,.55)]:
        x,y=xx*W,base-hh*H
        for k in range(160):
            r=8+k*1.6; x-=R.uniform(3,7); y-=R.uniform(.5,2.2)-k*.004
            cv2.circle(sm,(int(x+R.normal(0,6)),int(y+R.normal(0,5))),int(r),R.uniform(.05,.12),-1)
    return cv2.GaussianBlur(sm,(0,0),18)

WORDS={'sapr-labs':['ПЕРЕРЕГУЛИРОВАНИЕ','ТОК ЯКОРЯ','ЕЩЁ ОДИН КОНТУР'],'krrs-robot':['РАВНОВЕСИЕ','ПАДЕНИЕ','ОБРАТНАЯ СВЯЗЬ'],
       'op-coursework':['НАГРУЗКА','ЗАПАС ПРОЧНОСТИ','ПЕРЕДАТОЧНОЕ ЧИСЛО'],'eco-pdv':['ВЫБРОС','ПРЕДЕЛ','ВЕТЕР НЕ ПОМОЖЕТ']}

def grain(H,W,amt):
    g=R.normal(0,1,(H,W)).astype(np.float32); g=cv2.GaussianBlur(g,(0,0),.7); return g*amt

PALETTES={
    'выгоревший день': dict(day=True,  sky=('#c9e2d2','#f4efd6','#e9d9a8'), far='#9fb39a', near='#4e5e4e', smoke='#a9a189', text='#3a4136', frame='#f7f4ea', bokeh=('#fff6cf','#e9f7c8','#fffbe6'), leak=(1,.75,.3), cross=((-.04,.03,.05),(.02,.03,-.06))),
    'бирюзовая ночь':  dict(day=False, sky=('#06141a','#173a34','#4a3a17'), far='#03090b', near='#020506', smoke='#6f8a7c', text='#ffffff', frame='#0a0d0d', bokeh=('#f6a93b','#ffd27a','#a6e6c5','#e9f08a'), leak=(.35,.7,.55), cross=((-.04,.03,.05),(.02,.03,-.06))),
    'сепия':           dict(day=True,  sky=('#d9c7a5','#f1e3c4','#caa772'), far='#a8946e', near='#4d3f2c', smoke='#b59f7a', text='#3b2f22', frame='#f4ead6', bokeh=('#fff0c8','#ffe2a8'), leak=(1,.6,.25), cross=((.02,0,-.03),(.03,.01,-.05))),
    'рассвет':         dict(day=True,  sky=('#8fb0d8','#f2c9b8','#f6a96b'), far='#9a8fa8', near='#3f3b52', smoke='#c9a9a0', text='#2d2a3a', frame='#fbf1ea', bokeh=('#ffe0c8','#ffd0e0','#fff4d0'), leak=(1,.55,.45), cross=((-.02,0,.04),(.04,.02,-.04))),
    'смог':            dict(day=False, sky=('#1a1410','#4a3a24','#8a6a30'), far='#120d08', near='#070504', smoke='#8a7a5a', text='#ffe8c0', frame='#0d0b08', bokeh=('#ffb347','#ff8c42','#ffd27a'), leak=(.8,.45,.2), cross=((.02,0,-.04),(.05,.02,-.06))),
}
APPS=['sapr-labs','krrs-robot','op-coursework','eco-pdv']
SPEC=Spec('film',[
    Param('app','sapr-labs',kind='choice',choices=APPS+['нет'],group='сюжет',help='силуэт: ЛЭП, робот, балка и шестерни, трубы; «нет» — только город',rand=False),
    Param('palette','выгоревший день',kind='choice',choices=list(PALETTES),group='сюжет',help='плёнка и время суток'),
    Param('width',1920,320,4096,group='сюжет',help='ширина, px',rand=False), Param('height',1200,240,4096,group='сюжет',help='высота, px',rand=False),
    Param('sun',1.0,0.0,1.5,group='небо',help='солнце / зарево',rand=(0.0,1.2)), Param('sun_x',.78,0.0,1.0,group='небо',help='солнце по горизонтали'),
    Param('sun_y',.18,0.0,.8,group='небо',help='солнце по вертикали'), Param('horizon',.92,.6,1.0,group='небо',help='линия земли (доля высоты)',rand=(.85,.97)),
    Param('city',1.0,0.0,1.5,group='силуэты',help='дальний город'), Param('silhouette',1.0,0.0,1.2,group='силуэты',help='силуэт-сюжет утилиты',rand=(.6,1.2)),
    Param('smoke',1.0,0.0,3.0,group='силуэты',help='дым (у экологии)'), Param('windows',1.0,0.0,4.0,group='силуэты',help='огни окон ночью'),
    Param('words','авто',group='слова',help='реплики через «|»; «авто» — слова утилиты; пусто — без слов'),
    Param('word_size',130,40,260,group='слова',help='размер слов',rand=(80,200)), Param('word_opacity',1.0,0.0,2.0,group='слова',help='заметность слов'),
    Param('word_ghost',1.0,0.0,2.0,group='слова',help='двоение слов'),
    Param('bokeh',30,0,150,group='свет',help='число пятен боке',rand=(0,80)), Param('bokeh_size',42,5,150,group='свет',help='средний размер боке',rand=(15,90)),
    Param('leak',1.0,0.0,2.5,group='свет',help='засветка края плёнки'),
    Param('leak_side','авто',kind='choice',choices=['авто','справа','слева','сверху','снизу'],group='свет',help='откуда засветка'),
    Param('double',-1.0,-1.0,1.0,group='кадр',help='двойная экспозиция; −1 — как у палитры (ночью есть, днём нет)'),
    Param('aberration',3,0,14,group='кадр',help='хроматическая аберрация, px',rand=(0,8)),
    Param('insets',2,0,3,group='кадр',help='врезки сплит-экрана'), Param('inset_zoom',2.0,1.2,4.0,group='кадр',help='увеличение во врезках'),
    Param('bands',1.0,0.0,3.0,group='кадр',help='полосы развёртки (ночью)'), Param('grain',1.0,0.0,3.0,group='кадр',help='зерно'),
    Param('vignette',1.0,0.0,2.5,group='кадр',help='виньетка'), Param('cross',1.0,0.0,3.0,group='кадр',help='кросс-процесс (сдвиг теней и светов)'),
],{
    'день': {}, 'ночь': dict(palette='бирюзовая ночь'),
    'сепия': dict(palette='сепия', bokeh=10, insets=1, aberration=1),
    'рассвет': dict(palette='рассвет', sun=1.3, sun_x=.3, sun_y=.55, bokeh=60, words=''),
    'смог': dict(palette='смог', smoke=2.5, windows=2.5, bokeh=70, leak=1.6),
    'чистый кадр': dict(words='', insets=0, bokeh=0, double=0, aberration=0, leak=.3),
},title='Засветка: кадр',about='Кадр выжженной / ночной плёнки с силуэтом утилиты, словами, боке и сплит-врезками')

def frame(P, seed=3):
    global R
    R=np.random.default_rng(seed)
    W,H=int(P['width']),int(P['height']); pal=PALETTES[P['palette']]; day=pal['day']; base=H*P['horizon']; app=P['app']
    Y=np.linspace(0,1,H)[:,None,None]; top,mid,low=(hexc(c) for c in pal['sky']); k=.55 if day else .6
    sky=np.where(Y<k, top*(1-Y/k)+mid*(Y/k), mid*(1-(Y-k)/(1-k))+low*((Y-k)/(1-k)))
    img=np.broadcast_to(sky,(H,W,3)).astype(np.float32).copy()
    if P['sun']>0:
        sun=np.exp(-(((np.arange(W)[None,:]-P['sun_x']*W)/(.2*W))**2+((np.arange(H)[:,None]-P['sun_y']*H)/(.2*H))**2))*P['sun']
        tint=np.array([1,.98,.85]) if day else hexc(pal['bokeh'][0])*.6
        img=1-(1-img)*(1-np.clip(sun,0,1)[...,None]*tint)
    far=np.zeros((H,W),np.float32); skyline(far,W,H,base,int(R.integers(0,999))); far=np.clip(cv2.GaussianBlur(far,(0,0),6)*P['city'],0,1)
    near=np.zeros((H,W),np.float32)
    if app!='нет': motifs(near,app,W,H,base)
    near=np.clip(cv2.GaussianBlur(near,(0,0),2.2)*P['silhouette'],0,1)
    fa,na=(.32,.7) if day else (.7,.85)
    img=img*(1-far[...,None]*fa)+hexc(pal['far'])*far[...,None]*fa
    if not day and P['windows']>0:
        win=(R.random((H,W))<.0009*P['windows']).astype(np.float32)*far
        win=cv2.GaussianBlur(cv2.dilate(win,np.ones((3,2))),(0,0),1.2)*3
        img=img+win[...,None]*hexc(pal['bokeh'][0])*.8
    img=img*(1-near[...,None]*na)+hexc(pal['near'])*near[...,None]*na
    if app!='нет' and P['smoke']>0:
        sm=np.clip(smoke(W,H,app,base)*P['smoke']*(1.6 if day else 1),0,1)
        img=img*(1-sm[...,None])+hexc(pal['smoke'])*sm[...,None] if day else img+sm[...,None]*hexc(pal['smoke'])*.8
    bk=np.zeros((H,W,3),np.float32)
    for _ in range(int(P['bokeh'])):
        x=R.uniform(0,W); y=R.uniform(.05*H,.85*H) if day else R.uniform(.45*H,H); r=max(3,R.uniform(.33,1.66)*P['bokeh_size']*W/1920)
        col=hexc(pal['bokeh'][int(R.integers(0,len(pal['bokeh'])))])
        x0,y0,x1,y1=max(0,int(x-r*1.6)),max(0,int(y-r*1.6)),min(W,int(x+r*1.6)+1),min(H,int(y+r*1.6)+1)
        if x1<=x0 or y1<=y0: continue
        disc=np.zeros((y1-y0,x1-x0),np.float32); cv2.circle(disc,(int(x-x0),int(y-y0)),int(r),1,-1,cv2.LINE_AA); disc=cv2.GaussianBlur(disc,(0,0),2)
        ring=np.clip(disc-cv2.GaussianBlur(disc,(0,0),r*.25),0,1)
        bk[y0:y1,x0:x1]+=(disc*.22+ring*.25)[...,None]*col*R.uniform(.4,1)
    img=1-(1-img)*(1-np.clip(bk,0,1))
    side=P['leak_side'] if P['leak_side']!='авто' else ('справа' if day else 'слева')
    if side in ('справа','слева'): lk=np.exp(-((np.arange(W)[None,:]-(W if side=='справа' else 0))/(.28*W))**2)*np.ones((H,1))
    else: lk=np.exp(-((np.arange(H)[:,None]-(0 if side=='сверху' else H))/(.28*H))**2)*np.ones((1,W))
    img=1-(1-img)*(1-np.clip(lk[...,None]*np.array(pal['leak'])*(.55 if day else .25)*P['leak'],0,1))
    words=WORDS.get(app,[]) if P['words']=='авто' else [w.strip() for w in str(P['words']).split('|') if w.strip()]
    if words and P['word_opacity']>0:
        pil=Image.new('L',(W,H),0); dr=ImageDraw.Draw(pil)
        for i,wd in enumerate(words):
            sz=max(8,int(P['word_size']*R.uniform(.7,1.3)*W/1920))
            draw_text(dr,(int(R.uniform(.02,.45)*W),int((.12+i*(.78/max(1,len(words))))*H)),wd,'cond',sz,int(R.uniform(150,230)))
        txt=np.asarray(pil).astype(np.float32)/255
        ghost=cv2.GaussianBlur(np.roll(txt,(int(R.uniform(8,16)),int(R.uniform(20,40))),axis=(0,1)),(0,0),5)
        a=np.clip(txt*.32*P['word_opacity']+ghost*.18*P['word_ghost'],0,1)[...,None]
        if day: a=np.clip(a*1.25,0,1); img=img*(1-a)+hexc(pal['text'])*a
        else: img=img*(1-a)+hexc(pal['text'])*a
    dbl=P['double'] if P['double']>=0 else (0 if day else 1)
    if dbl>0:
        sh=np.roll(img,(0,int(.04*W)),axis=(0,1)); img=np.clip(img*(1-.22*dbl)+sh*.32*dbl,0,1)
    if not day and P['bands']>0:
        img=img*(1+(.07*np.sin(np.arange(H)[:,None]/7.0)+.05*(R.random((H,1))-.5))*P['bands'])[...,None]
    if day: img=np.clip((img-.04)*1.12,0,1)
    L=img.mean(2,keepdims=True); cs,ch=(np.array(v,np.float32) for v in pal['cross'])
    img=img+((1-L)*cs+L*ch)*P['cross']
    a=int(P['aberration'])
    if a: img=np.dstack([np.roll(img[...,0],a,axis=1),img[...,1],np.roll(img[...,2],-a,axis=1)])
    out=img.copy(); fr=hexc(pal['frame']); t=max(3,W//190)
    FOC={'sapr-labs':[(.56,.32),(.27,.55),(.62,.12)],'krrs-robot':[(.55,.62),(.6,.3),(.4,.5)],'op-coursework':[(.12,.45),(.55,.25),(.3,.5)],
         'eco-pdv':[(.5,.12),(.58,.55),(.7,.3)],'нет':[(.4,.6),(.6,.7),(.5,.5)]}[app]
    for (x0,y0,ww,hh),(zx,zy) in list(zip([(.06,.08,.24,.3),(.7,.62,.26,.3),(.7,.08,.24,.26)],FOC))[:int(P['insets'])]:
        X0,Y0,WW,HH=int(x0*W),int(y0*H),int(ww*W),int(hh*H); z=P['inset_zoom']
        crop=img[int(zy*H):int(zy*H+HH/z),int(zx*W):int(zx*W+WW/z)]
        if crop.size: out[Y0:Y0+HH,X0:X0+WW]=cv2.resize(np.ascontiguousarray(crop),(WW,HH),interpolation=cv2.INTER_CUBIC)
        cv2.rectangle(out,(X0,Y0),(X0+WW,Y0+HH),tuple(float(v) for v in fr),t)
    img=out+grain(H,W,(.05 if day else .07)*P['grain'])[...,None]
    Yv,Xv=np.mgrid[0:H,0:W]; v=np.clip(1-.35*P['vignette']*(((Xv/W-.5)**2+(Yv/H-.5)**2)*2.4),0,1)
    img=img*(v[...,None] if not day else (0.85+0.15*v)[...,None])
    return np.clip(img,0,1)

apply = frame
