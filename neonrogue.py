#!/usr/bin/env python3
"""NEONROGUE: roguelike cyberpunk para la terminal.

Eres un netrunner que baja por los pisos de la torre Arasaka-no-oficial
buscando el núcleo de datos. Sin dependencias: solo Python 3 y curses.

    python3 neonrogue.py            # jugar
    python3 neonrogue.py --semilla 42
"""
import argparse
import curses
import random
from dataclasses import dataclass, field

ANCHO, ALTO = 78, 21
VISION = 8
PISOS = 8

PARED, SUELO, PUERTA, BAJADA, NUCLEO = '#', '.', '+', '>', '*'

# colores: 1 rosa, 2 cian, 3 amarillo, 4 verde, 5 morado, 6 rojo, 7 tenue
ENEMIGOS = [
    # nombre, letra, color, hp, ataque, defensa, xp, piso mínimo
    ('dron de seguridad', 'd', 2, 4, 2, 0, 3, 1),
    ('pandillero chrome', 'p', 1, 7, 3, 1, 5, 1),
    ('perro cibernético', 'c', 3, 6, 4, 0, 6, 2),
    ('ICE negro', 'I', 5, 10, 5, 2, 10, 3),
    ('mech de asalto', 'M', 6, 18, 6, 3, 18, 5),
    ('IA rebelde', 'A', 5, 26, 8, 4, 30, 7),
]
OBJETOS = [
    # nombre, letra, color, efecto, valor
    ('stim médico', '!', 4, 'hp', 8),
    ('chip de RAM', '%', 2, 'ram', 3),
    ('granada EMP', '?', 3, 'emp', 0),
    ('mejora de brazo', '/', 1, 'ataque', 1),
    ('placa subdérmica', '[', 5, 'defensa', 1),
    ('eddies', '$', 3, 'oro', 0),
]


@dataclass
class Ente:
    x: int
    y: int
    letra: str
    color: int
    nombre: str
    hp: int
    hp_max: int
    ataque: int
    defensa: int
    xp: int = 0
    aturdido: int = 0
    visto: bool = False


@dataclass
class Jugador(Ente):
    ram: int = 6
    ram_max: int = 6
    nivel: int = 1
    exp: int = 0
    oro: int = 0
    emp: int = 1
    bajas: int = 0
    inventario: list = field(default_factory=list)


class Sala:
    def __init__(self, x, y, w, h):
        self.x1, self.y1, self.x2, self.y2 = x, y, x + w, y + h

    def centro(self):
        return (self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2

    def choca(self, o):
        return self.x1 <= o.x2 + 1 and self.x2 + 1 >= o.x1 and self.y1 <= o.y2 + 1 and self.y2 + 1 >= o.y1


class Juego:
    def __init__(self, semilla):
        self.r = random.Random(semilla)
        self.semilla = semilla
        self.piso = 1
        self.log = []
        self.j = Jugador(0, 0, '@', 3, 'tú', 20, 20, 3, 1)
        self.fin = None
        self.nuevo_piso()
        self.msg('Conectado. Baja hasta el núcleo de datos del piso %d.' % PISOS, 2)

    # ---------- mapa ----------
    def nuevo_piso(self):
        r = self.r
        self.mapa = [[PARED] * ANCHO for _ in range(ALTO)]
        self.visto = [[False] * ANCHO for _ in range(ALTO)]
        self.salas = []
        for _ in range(60):
            w, h = r.randint(6, 14), r.randint(4, 7)
            s = Sala(r.randint(1, ANCHO - w - 2), r.randint(1, ALTO - h - 2), w, h)
            if any(s.choca(o) for o in self.salas):
                continue
            for y in range(s.y1, s.y2):
                for x in range(s.x1, s.x2):
                    self.mapa[y][x] = SUELO
            if self.salas:
                (ax, ay), (bx, by) = self.salas[-1].centro(), s.centro()
                if r.random() < .5:
                    self.tunel_h(ax, bx, ay); self.tunel_v(ay, by, bx)
                else:
                    self.tunel_v(ay, by, ax); self.tunel_h(ax, bx, by)
            self.salas.append(s)
            if len(self.salas) >= 11:
                break
        self.j.x, self.j.y = self.salas[0].centro()
        fx, fy = self.salas[-1].centro()
        self.mapa[fy][fx] = NUCLEO if self.piso == PISOS else BAJADA
        self.enemigos, self.objetos = [], []
        for s in self.salas[1:]:
            for _ in range(r.randint(0, 1 + self.piso // 3)):
                self.poner_enemigo(s)
            if r.random() < .55:
                self.poner_objeto(s)
        if self.piso == PISOS:  # el jefe cuida el núcleo
            jefe = ENEMIGOS[-1]
            self.enemigos.append(Ente(fx - 1, fy, jefe[1], jefe[2], 'IA guardiana', 40, 40, 9, 5, 60))

    def tunel_h(self, x1, x2, y):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            self.mapa[y][x] = SUELO

    def tunel_v(self, y1, y2, x):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            self.mapa[y][x] = SUELO

    def libre(self, s):
        for _ in range(20):
            x, y = self.r.randint(s.x1, s.x2 - 1), self.r.randint(s.y1, s.y2 - 1)
            if self.mapa[y][x] == SUELO and not self.ente_en(x, y) and not self.objeto_en(x, y):
                return x, y
        return None

    def poner_enemigo(self, s):
        posibles = [e for e in ENEMIGOS[:-1] if e[7] <= self.piso] or ENEMIGOS[:1]
        n, l, c, hp, at, de, xp, _ = self.r.choice(posibles)
        p = self.libre(s)
        if p:
            extra = self.piso // 3
            self.enemigos.append(Ente(p[0], p[1], l, c, n, hp + extra * 2, hp + extra * 2, at + extra, de, xp))

    def poner_objeto(self, s):
        o = self.r.choices(OBJETOS, weights=[5, 3, 2, 1, 1, 4])[0]
        p = self.libre(s)
        if p:
            self.objetos.append([p[0], p[1], o])

    def ente_en(self, x, y):
        return next((e for e in self.enemigos if e.x == x and e.y == y), None)

    def objeto_en(self, x, y):
        return next((o for o in self.objetos if o[0] == x and o[1] == y), None)

    def transparente(self, x, y):
        return 0 <= x < ANCHO and 0 <= y < ALTO and self.mapa[y][x] != PARED

    def ve(self, x0, y0, x1, y1):
        """Línea de Bresenham: ¿hay pared entre los dos puntos?"""
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while (x0, y0) != (x1, y1):
            if self.mapa[y0][x0] == PARED:
                return False
            e2 = 2 * err
            if e2 >= dy:
                err += dy; x0 += sx
            if e2 <= dx:
                err += dx; y0 += sy
        return True

    def campo_visual(self):
        vis = set()
        jx, jy = self.j.x, self.j.y
        for y in range(max(0, jy - VISION), min(ALTO, jy + VISION + 1)):
            for x in range(max(0, jx - VISION * 2), min(ANCHO, jx + VISION * 2 + 1)):
                if ((x - jx) / 2) ** 2 + (y - jy) ** 2 <= VISION ** 2 and self.ve(jx, jy, x, y):
                    vis.add((x, y))
                    self.visto[y][x] = True
        return vis

    # ---------- acciones ----------
    def msg(self, t, color=7):
        self.log.append((t, color))
        self.log = self.log[-4:]

    def mover(self, dx, dy):
        nx, ny = self.j.x + dx, self.j.y + dy
        e = self.ente_en(nx, ny)
        if e:
            self.atacar(self.j, e)
        elif self.transparente(nx, ny):
            self.j.x, self.j.y = nx, ny
            o = self.objeto_en(nx, ny)
            if o:
                self.recoger(o)
            if self.mapa[ny][nx] == BAJADA:
                self.msg('Ascensor de servicio. Pulsa > para bajar.', 3)
            if self.mapa[ny][nx] == NUCLEO:
                if any(e.nombre == 'IA guardiana' for e in self.enemigos):
                    self.msg('La IA guardiana bloquea el núcleo.', 6)
                else:
                    self.fin = 'victoria'
        else:
            return False
        return True

    def atacar(self, a, b):
        dano = max(1, a.ataque + self.r.randint(-1, 2) - b.defensa)
        critico = self.r.random() < .1
        if critico:
            dano *= 2
        b.hp -= dano
        if a is self.j:
            self.msg(f'Golpeas al {b.nombre}: {dano}{" ¡CRÍTICO!" if critico else ""}', 1 if critico else 7)
            if b.hp <= 0:
                self.enemigos.remove(b)
                self.j.bajas += 1
                self.ganar_xp(b.xp)
                self.msg(f'{b.nombre.capitalize()} desconectado. +{b.xp} XP', 4)
                if self.r.random() < .25:
                    self.objetos.append([b.x, b.y, OBJETOS[5]])
        else:
            self.msg(f'El {a.nombre} te pega: {dano}', 6)
            if b.hp <= 0:
                self.fin = f'eliminado por un {a.nombre}'

    def ganar_xp(self, n):
        j = self.j
        j.exp += n
        while j.exp >= j.nivel * 15:
            j.exp -= j.nivel * 15
            j.nivel += 1
            j.hp_max += 5; j.hp = j.hp_max
            j.ram_max += 1; j.ram = j.ram_max
            j.ataque += 1
            self.msg(f'¡NIVEL {j.nivel}! Más vida, RAM y ataque.', 3)

    def recoger(self, o):
        self.objetos.remove(o)
        n, _, _, ef, v = o[2]
        j = self.j
        if ef == 'hp':
            j.hp = min(j.hp_max, j.hp + v)
        elif ef == 'ram':
            j.ram = min(j.ram_max, j.ram + v)
        elif ef == 'emp':
            j.emp += 1
        elif ef == 'ataque':
            j.ataque += v
        elif ef == 'defensa':
            j.defensa += v
        elif ef == 'oro':
            v = self.r.randint(5, 20) * self.piso
            j.oro += v
            n = f'{v} eddies'
        self.msg(f'Recoges: {n}.', 4)

    def hackear(self, vis):
        """Gasta 3 de RAM: daño a todos los enemigos a la vista."""
        if self.j.ram < 3:
            self.msg('Falta RAM (3).', 6)
            return False
        objetivos = [e for e in self.enemigos if (e.x, e.y) in vis]
        if not objetivos:
            self.msg('No hay nada que hackear a la vista.', 7)
            return False
        self.j.ram -= 3
        for e in list(objetivos):
            dano = 3 + self.j.nivel
            e.hp -= dano
            if e.hp <= 0:
                self.enemigos.remove(e); self.j.bajas += 1; self.ganar_xp(e.xp)
        self.msg(f'Quickhack: cortocircuito a {len(objetivos)} objetivo(s).', 2)
        return True

    def emp(self, vis):
        if not self.j.emp:
            self.msg('No tienes granadas EMP.', 6)
            return False
        self.j.emp -= 1
        n = 0
        for e in self.enemigos:
            if (e.x, e.y) in vis:
                e.aturdido = 4; n += 1
        self.msg(f'¡EMP! {n} enemigo(s) aturdidos 4 turnos.', 3)
        return True

    def bajar(self):
        if self.mapa[self.j.y][self.j.x] != BAJADA:
            self.msg('Aquí no hay ascensor.', 7)
            return False
        self.piso += 1
        self.j.hp = min(self.j.hp_max, self.j.hp + 5)
        self.nuevo_piso()
        self.msg(f'Piso {self.piso}. La seguridad es más dura.', 5)
        return True

    def turno_enemigos(self, vis):
        for e in list(self.enemigos):
            if e.aturdido:
                e.aturdido -= 1
                continue
            if (e.x, e.y) in vis:
                e.visto = True
            if not e.visto:
                continue
            dx, dy = self.j.x - e.x, self.j.y - e.y
            if max(abs(dx), abs(dy)) == 1:
                self.atacar(e, self.j)
                if self.fin:
                    return
                continue
            pasos = sorted([(0, 0), ((dx > 0) - (dx < 0), 0), (0, (dy > 0) - (dy < 0)), ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))],
                           key=lambda p: abs(self.j.x - e.x - p[0]) + abs(self.j.y - e.y - p[1]))
            for px, py in pasos:
                nx, ny = e.x + px, e.y + py
                if (px or py) and self.transparente(nx, ny) and not self.ente_en(nx, ny) and (nx, ny) != (self.j.x, self.j.y):
                    e.x, e.y = nx, ny
                    break
        if self.r.random() < .08:
            self.j.ram = min(self.j.ram_max, self.j.ram + 1)

    def puntaje(self):
        return self.j.oro + self.j.bajas * 10 + (self.piso - 1) * 100 + (1000 if self.fin == 'victoria' else 0)


# ---------- pantalla ----------
def colores():
    curses.start_color()
    try:
        curses.use_default_colors(); fondo = -1
    except curses.error:
        fondo = curses.COLOR_BLACK
    pares = [curses.COLOR_MAGENTA, curses.COLOR_CYAN, curses.COLOR_YELLOW, curses.COLOR_GREEN, curses.COLOR_BLUE, curses.COLOR_RED, curses.COLOR_WHITE]
    for i, c in enumerate(pares, 1):
        curses.init_pair(i, c, fondo)
    if curses.COLORS >= 256:  # neón de verdad si la terminal lo permite
        for i, c in enumerate([199, 51, 226, 46, 135, 196, 60], 1):
            curses.init_pair(i, c, fondo)


def P(n, b=False):
    return curses.color_pair(n) | (curses.A_BOLD if b else 0)


def barra(v, m, largo=12):
    llenos = max(0, round(v / m * largo))
    return '█' * llenos + '░' * (largo - llenos)


def dibujar(scr, g, vis):
    scr.erase()
    alto, ancho = scr.getmaxyx()
    if alto < ALTO + 7 or ancho < ANCHO + 2:
        scr.addstr(0, 0, f'Agranda la terminal a {ANCHO + 2}x{ALTO + 7} como mínimo.')
        scr.refresh(); return
    j = g.j
    scr.addstr(0, 0, ' NEON', P(1, True)); scr.addstr('ROGUE ', P(2, True))
    scr.addstr(f' PISO {g.piso}/{PISOS}  NIVEL {j.nivel}  ', P(7))
    scr.addstr(f'¥ {j.oro}', P(3, True))
    pared_c = [5, 2, 1, 5, 2, 1, 5, 6][g.piso - 1]
    for y in range(ALTO):
        for x in range(ANCHO):
            if not g.visto[y][x]:
                continue
            ch = g.mapa[y][x]
            en_vista = (x, y) in vis
            if ch == PARED:
                atr = P(pared_c, en_vista) if en_vista else P(7)
            elif ch in (BAJADA, NUCLEO):
                atr = P(3, True) | (curses.A_BLINK if ch == NUCLEO else 0)
            else:
                atr = P(7) if not en_vista else P(7) | curses.A_BOLD
                ch = '·' if en_vista else ' '
            scr.addstr(y + 1, x, ch, atr)
    for o in g.objetos:
        if (o[0], o[1]) in vis:
            scr.addstr(o[1] + 1, o[0], o[2][1], P(o[2][2], True))
    for e in g.enemigos:
        if (e.x, e.y) in vis:
            scr.addstr(e.y + 1, e.x, e.letra, P(e.color, True) | (curses.A_DIM if e.aturdido else 0))
    scr.addstr(j.y + 1, j.x, '@', P(3, True))
    y0 = ALTO + 1
    scr.addstr(y0, 0, 'HP  ', P(6, True)); scr.addstr(barra(j.hp, j.hp_max), P(6)); scr.addstr(f' {j.hp}/{j.hp_max}  ', P(7))
    scr.addstr('RAM ', P(2, True)); scr.addstr(barra(j.ram, j.ram_max, 8), P(2)); scr.addstr(f' {j.ram}/{j.ram_max}  ', P(7))
    scr.addstr('XP ', P(4, True)); scr.addstr(barra(j.exp, j.nivel * 15, 8), P(4))
    scr.addstr(y0 + 1, 0, f'ATQ {j.ataque}  DEF {j.defensa}  EMP {j.emp}  BAJAS {j.bajas}', P(7))
    scr.addstr(y0 + 1, 44, 'mover hjkl/flechas · h(a)ck · (e)mp · > bajar · ? ayuda', P(7))
    for i, (t, c) in enumerate(g.log):
        scr.addstr(y0 + 2 + i, 0, ('> ' + t)[:ANCHO], P(c, i == len(g.log) - 1))
    scr.refresh()


AYUDA = """
  NEONROGUE · cómo jugar

  @  tú, el netrunner            >  ascensor al piso siguiente
  *  núcleo de datos (piso 8)    #  paredes de la torre

  d dron   p pandillero   c perro cibernético
  I ICE negro   M mech   A IA rebelde

  !  stim (vida)     %  chip de RAM     ?  granada EMP
  /  mejora de brazo [  placa subdérmica  $  eddies

  Movimiento: flechas, hjkl o yubn en diagonal. Choca para atacar.
  a  quickhack: gasta 3 RAM y daña a todos los enemigos a la vista
  e  EMP: aturde 4 turnos a todos los enemigos a la vista
  .  esperar un turno     >  bajar     q  salir

  Pulsa una tecla para volver.
"""

TITULO = r"""
 _   _ _____ ___  _   _ ____   ___   ____ _   _ _____
| \ | | ____/ _ \| \ | |  _ \ / _ \ / ___| | | | ____|
|  \| |  _|| | | |  \| | |_) | | | | |  _| | | |  _|
| |\  | |__| |_| | |\  |  _ <| |_| | |_| | |_| | |___
|_| \_|_____\___/|_| \_|_| \_\\___/ \____|\___/|_____|
"""


def pantalla_texto(scr, texto, color=2):
    scr.erase()
    for i, l in enumerate(texto.split('\n')):
        try:
            scr.addstr(i, 2, l, P(color, i < 7))
        except curses.error:
            pass
    scr.refresh()
    scr.getch()


def jugar(scr, semilla):
    curses.curs_set(0)
    colores()
    pantalla_texto(scr, TITULO + '\n   Infíltrate en la torre, baja 8 pisos y roba el núcleo de datos.\n\n   [ pulsa una tecla para conectarte ]', 1)
    g = Juego(semilla)
    teclas = {
        curses.KEY_LEFT: (-1, 0), curses.KEY_RIGHT: (1, 0), curses.KEY_UP: (0, -1), curses.KEY_DOWN: (0, 1),
        ord('h'): (-1, 0), ord('l'): (1, 0), ord('k'): (0, -1), ord('j'): (0, 1),
        ord('y'): (-1, -1), ord('u'): (1, -1), ord('b'): (-1, 1), ord('n'): (1, 1),
    }
    while not g.fin:
        vis = g.campo_visual()
        dibujar(scr, g, vis)
        k = scr.getch()
        hecho = False
        if k in teclas:
            hecho = g.mover(*teclas[k])
        elif k == ord('a'):
            hecho = g.hackear(vis)
        elif k == ord('e'):
            hecho = g.emp(vis)
        elif k == ord('>'):
            hecho = g.bajar()
        elif k == ord('.'):
            hecho = True
        elif k == ord('?'):
            pantalla_texto(scr, AYUDA)
        elif k in (ord('q'), 27):
            g.fin = 'desconectado'
        if hecho and not g.fin:
            g.turno_enemigos(g.campo_visual())
    victoria = g.fin == 'victoria'
    final = (TITULO + ('\n   ACCESS GRANTED: robaste el núcleo de datos.' if victoria else f'\n   FLATLINE: {g.fin}.')
             + f'\n\n   piso {g.piso} · nivel {g.j.nivel} · bajas {g.j.bajas} · ¥ {g.j.oro}'
             + f'\n   PUNTAJE: {g.puntaje()}    semilla: {g.semilla}\n\n   [ pulsa una tecla ]')
    pantalla_texto(scr, final, 4 if victoria else 6)
    return g.puntaje()


def main():
    ap = argparse.ArgumentParser(description='Roguelike cyberpunk para la terminal.')
    ap.add_argument('--semilla', type=int, default=None, help='misma semilla = misma torre')
    a = ap.parse_args()
    semilla = a.semilla if a.semilla is not None else random.randrange(100000)
    pts = curses.wrapper(jugar, semilla)
    print(f'NEONROGUE · puntaje {pts} · semilla {semilla}')


if __name__ == '__main__':
    main()
