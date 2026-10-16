"""Generate the checked-in vector catalog; no network or image runtime needed."""
from __future__ import annotations
import hashlib
import html
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from game_config import NEW_ITEMS, ENTERPRISES, BUSINESS_CASES, COLLECTION_CASES
from services.content import asset_slug
from seed_data import CASES

ROOT = Path(__file__).resolve().parents[1] / "web/assets"


def svg(name, body, accent="#d6b16b", serial="COLLECTION"):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480" role="img" aria-label="{html.escape(name)}">
    <defs><radialGradient id="bg"><stop stop-color="#29261e"/><stop offset="1" stop-color="#090a0c"/></radialGradient>
    <linearGradient id="metal" x2=".8" y2="1"><stop stop-color="#faf0ce"/><stop offset=".18" stop-color="{accent}"/><stop offset=".5" stop-color="#65502d"/><stop offset=".72" stop-color="{accent}"/><stop offset="1" stop-color="#eee0b7"/></linearGradient>
    <linearGradient id="body" x2=".6" y2="1"><stop stop-color="#55575a"/><stop offset=".35" stop-color="#25272a"/><stop offset=".7" stop-color="#0c0e11"/><stop offset="1" stop-color="#343536"/></linearGradient>
    <linearGradient id="glass" x2="1" y2="1"><stop stop-color="#8c9a9e"/><stop offset=".3" stop-color="#29353d"/><stop offset="1" stop-color="#10151a"/></linearGradient>
    <filter id="shadow"><feGaussianBlur stdDeviation="12"/></filter></defs>
    <rect width="640" height="480" fill="url(#bg)"/><ellipse cx="320" cy="365" rx="215" ry="19" fill="#000" opacity=".8" filter="url(#shadow)"/>
    <path d="M70 386H570M105 392H535" stroke="{accent}" opacity=".17"/>
    <g stroke-linejoin="round">{body}</g><text x="38" y="39" fill="{accent}" font-family="Arial,sans-serif" font-size="10" letter-spacing="4">SHAMA WORLD / {serial}</text>
    <text x="320" y="439" text-anchor="middle" fill="#efebe1" font-family="Arial,sans-serif" font-size="17" letter-spacing="1">{html.escape(name)}</text></svg>'''


def item_body(category,variant,index):
    accent = ["#d6b16b","#c4c8c9","#b67c4b","#e2cd9b"][index%4]
    if variant in ("gold","villa","skeleton","imperial","trophy","chain"):
        accent="#e1bc65"
    if category == "CAR":
        roof=150+(index%3)*12
        body=f'<path d="M96 278L133 233L210 {roof}H388L466 222L541 252L553 309L507 331H139L87 310Z" fill="url(#body)" stroke="{accent}" stroke-width="3"/><path d="M195 229L229 {roof+17}H310V229ZM324 {roof+17}H380L439 229H324Z" fill="url(#glass)" stroke="#767c7d"/><path d="M104 279L231 265H426L537 261M250 249V312M427 248L451 310" fill="none" stroke="{accent}" opacity=".7"/><path d="M109 274L164 266L159 279L107 288M498 266L540 276" stroke="#fff4ca" stroke-width="7"/><path d="M94 299H145M482 301H548" stroke="#07080a" stroke-width="13"/>'
        for x in (186,465):
            body+=f'<circle cx="{x}" cy="313" r="43" fill="#07080a" stroke="#3f4144" stroke-width="5"/><circle cx="{x}" cy="313" r="28" fill="url(#metal)"/><circle cx="{x}" cy="313" r="20" fill="#17191b"/>'
            for a in range(0,360,60): body+=f'<path d="M{x} 288V338" stroke="{accent}" stroke-width="3" transform="rotate({a} {x} 313)"/>'
    elif category == "PROPERTY":
        height=145+(index%3)*22
        body=f'<path d="M127 340V{height}L323 {height-48}L510 {height+25}V340Z" fill="url(#body)" stroke="#676359" stroke-width="2"/><path d="M323 {height-48}V340M120 {height}L321 {height-58}L518 {height+20}" fill="none" stroke="{accent}" stroke-width="7"/>'
        for r in range(3):
            for j in range(5):
                x,y=155+j*65,height+28+r*48
                body+=f'<rect x="{x}" y="{y}" width="38" height="30" fill="url(#glass)" stroke="{accent}" opacity="{.4+(j%3)*.2}"/>'
        body+='<path d="M100 348H541L558 367H83Z" fill="url(#metal)"/><path d="M364 340V285H419V340" fill="#06080b" stroke="#8c7a51"/>'
    elif category == "CLOTHING":
        body=f'<path d="M252 129Q320 98 388 129L466 184L422 260L387 237L394 350H246L253 237L215 260L174 184Z" fill="url(#body)" stroke="{accent}" stroke-width="3"/><path d="M270 122Q265 190 320 193Q375 190 370 122Q320 92 270 122Z" fill="#141619" stroke="{accent}"/><path d="M320 193V348M250 330H390M204 192L237 223M401 223L439 192" stroke="{accent}" opacity=".6"/><path d="M280 267H360L369 312H271Z" fill="#1a1c1f" stroke="#555049"/><text x="349" y="238" fill="{accent}" font-family="serif" font-size="20">{index+1:02}</text>'
    elif category == "SNEAKERS" or variant == "boot":
        body=f'<path d="M164 175L240 154L286 245L383 270L489 283L515 328L492 350H133L114 326L143 269Z" fill="url(#body)" stroke="{accent}" stroke-width="4"/><path d="M126 320L505 319L515 339L495 357H128L112 341Z" fill="url(#metal)"/><path d="M261 234L324 283L391 276L286 310L226 281Z" fill="{accent}"/><path d="M183 181L238 176L263 237L171 251Z" fill="#26292c" stroke="#68635b"/>'
        for y in range(231,281,12): body+=f'<path d="M235 {y}L287 {y+7}" stroke="#ddd5c0" stroke-width="5"/>'
    elif category == "WATCH" or variant == "smartwatch":
        body='<path d="M275 76H365L377 181H263ZM263 302H377L362 397H278Z" fill="url(#body)" stroke="#88774d" stroke-width="3"/>'
        if variant == "smartwatch":
            body+='<rect x="234" y="163" width="172" height="168" rx="38" fill="url(#metal)"/><rect x="245" y="174" width="150" height="145" rx="30" fill="#070a0d"/><text x="320" y="257" text-anchor="middle" fill="#efd596" font-family="Arial" font-size="36">10:09</text>'
        else:
            body+='<circle cx="320" cy="243" r="100" fill="url(#metal)"/><circle cx="320" cy="243" r="86" fill="#12161a" stroke="#ada27e" stroke-width="2"/>'
            for a in range(0,360,30): body+=f'<path d="M320 166V177" stroke="{accent}" stroke-width="4" transform="rotate({a} 320 243)"/>'
            body+='<circle cx="288" cy="251" r="22" fill="url(#body)" stroke="#88774d"/><circle cx="351" cy="251" r="22" fill="url(#body)" stroke="#88774d"/><path d="M320 243L279 210M320 243L359 190" stroke="#eee1b8" stroke-width="5"/><path d="M320 243V307" stroke="#c59c43" stroke-width="2"/><circle cx="320" cy="243" r="5" fill="#eee1b8"/><rect x="421" y="224" width="14" height="29" rx="4" fill="url(#metal)"/>'
    elif category == "METAL":
        body=f'<path d="M164 205L367 147L489 230L287 296Z" fill="url(#metal)" stroke="#d4c49a" stroke-width="2"/><path d="M164 205V279L287 359V296Z" fill="#635239"/><path d="M287 296L489 230V302L287 359Z" fill="#a68b59"/><path d="M191 205L364 162L460 228L287 278Z" fill="none" stroke="#4d3f29"/><text x="320" y="231" text-anchor="middle" fill="#4d3f29" font-family="serif" font-size="22" transform="rotate(10 320 231)">FINE / {index+1:03}</text>'
    elif category == "TROPHY":
        if variant == "medal":
            body='<path d="M230 85H282L339 223H279ZM358 85H410L351 223H291Z" fill="url(#body)" stroke="#c6a363"/><circle cx="320" cy="279" r="80" fill="url(#metal)"/><circle cx="320" cy="279" r="64" fill="none" stroke="#665332" stroke-width="3"/><path d="M320 236L331 266L362 267L337 287L346 319L320 300L294 319L303 287L278 267L309 266Z" fill="#f5e3b4"/>'
        else:
            body='<path d="M247 137H393L376 243Q363 273 320 282Q277 273 264 243Z" fill="url(#metal)" stroke="#f6e3b2"/><path d="M247 154H198Q185 224 270 242M393 154H442Q455 224 370 242" fill="none" stroke="#b48c47" stroke-width="14"/><path d="M310 278H330V326H363V341H277V326H310Z" fill="url(#metal)"/><path d="M254 340H386L399 364H241Z" fill="url(#body)" stroke="#a69269"/>'
    elif variant == "headphones":
        body='<path d="M207 279V221Q207 109 320 109Q433 109 433 221V279" fill="none" stroke="#11151a" stroke-width="42"/><path d="M208 233V213Q208 113 320 113Q432 113 432 213V233" fill="none" stroke="#b8995f" stroke-width="6"/><rect x="178" y="220" width="64" height="123" rx="26" fill="url(#body)" stroke="#c3a367" stroke-width="3"/><rect x="398" y="220" width="64" height="123" rx="26" fill="url(#body)" stroke="#c3a367" stroke-width="3"/>'
    elif variant in ("tablet","phone"):
        w=134 if variant=="phone" else 230
        body=f'<rect x="{320-w//2}" y="105" width="{w}" height="253" rx="22" fill="url(#metal)"/><rect x="{326-w//2}" y="112" width="{w-12}" height="237" rx="18" fill="#080c11"/><path d="M{330-w//2} 290L{310+w//2} 173V334H{330-w//2}Z" fill="url(#glass)"/><circle cx="320" cy="119" r="3" fill="#d1bc86"/>'
    elif variant == "cap":
        body='<path d="M197 282Q193 161 320 153Q432 169 432 283Z" fill="url(#body)" stroke="#b49764" stroke-width="3"/><path d="M198 280Q281 264 430 281L489 317Q402 360 244 332L177 307Z" fill="url(#body)" stroke="#b49764" stroke-width="3"/><path d="M319 158V274" stroke="#b49764"/><text x="322" y="247" text-anchor="middle" fill="#d8b879" font-size="35" font-family="serif">S</text>'
    else:
        body='<ellipse cx="320" cy="233" rx="108" ry="121" fill="none" stroke="#63491e" stroke-width="22"/><ellipse cx="320" cy="229" rx="108" ry="121" fill="none" stroke="url(#metal)" stroke-width="13" stroke-dasharray="12 5"/><path d="M292 337H348L337 382H303Z" fill="url(#metal)"/>'
    return body,accent


def case_body(index,style):
    color={"bronze":"#bc8d56","gold":"#e5be67","platinum":"#d0d5d4","imperial":"#e7cf8f","carbon":"#c7ac70"}.get(style,"#d2ad65")
    x=145+(index%3)*8
    body=f'<path d="M{x} 185L365 140L507 205V334L286 386L{x} 322Z" fill="url(#body)" stroke="{color}" stroke-width="3"/><path d="M{x} 185L365 140L507 205L286 254Z" fill="#292b2d" stroke="{color}" stroke-width="3"/><path d="M286 254V386M{x} 220L286 286L507 239" stroke="{color}" stroke-width="5" fill="none"/><path d="M260 164V137L339 121L359 132V151" fill="none" stroke="{color}" stroke-width="10"/><path d="M{x+24} 198V333M{x+62} 208V348M461 218V345M423 229V354" fill="none" stroke="{color}" stroke-width="8"/><path d="M298 291L342 282V318L298 328Z" fill="url(#metal)"/><path d="M176 248L258 285V326L176 289Z" fill="#121517" stroke="#62563b"/><text x="204" y="285" fill="{color}" font-family="serif" font-size="19" transform="rotate(24 204 285)">{index+1:02}</text>'
    for r in range(index%4+1): body+=f'<path d="M{355+r*17} {336-r*4}V{360-r*4}" stroke="{color}" stroke-width="5"/>'
    return body,color


def generate():
    for index,(name,category,rarity,value,variant) in enumerate(NEW_ITEMS):
        body,color=item_body(category,variant,index)
        (ROOT/"items"/f"{asset_slug(name)}.svg").write_text(svg(name,body,color,f"{category} / {index+1:03}"),encoding="utf-8")
    (ROOT/"enterprises").mkdir(exist_ok=True)
    for index,(code,name,*_) in enumerate(ENTERPRISES):
        body,color=item_body("PROPERTY",code,index)
        body+=f'<rect x="231" y="224" width="178" height="25" fill="#15171a"/><text x="320" y="241" text-anchor="middle" fill="#d6b16b" font-size="12" font-family="Arial">{html.escape(name)}</text>'
        (ROOT/"enterprises"/f"{code}.svg").write_text(svg(name,body,color,"ENTERPRISE"),encoding="utf-8")
    for index,case in enumerate((*CASES,*COLLECTION_CASES,*BUSINESS_CASES)):
        body,color=case_body(index,case.get("style",["carbon","bronze","platinum","gold","imperial"][index%5]))
        (ROOT/"cases"/f"{asset_slug(case['name'])}.svg").write_text(svg(case['name'],body,color,"VAULT SERIES"),encoding="utf-8")
    print("Generated 35 item, 9 enterprise and 14 case vector assets")


if __name__ == "__main__":
    generate()
