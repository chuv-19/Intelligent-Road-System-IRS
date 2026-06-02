import sys, json, os, time
from PyQt6.QtWidgets import *
from PyQt6.QtGui import QPainter, QColor, QPen, QIcon, QPixmap, QTransform
from PyQt6.QtCore import Qt, QTimer
import sqlite3

try: import serial; HAS_SERIAL = True
except: HAS_SERIAL = False

M = r"C:\Users\elshi\Desktop\de_exam\media"
DB_FILE = r"events.db"
MAP_FILE = r"map.json"

LOGO = f"{M}\\TLgreen.png"
IMG1, IMG2, IMG3, IMG4, IMG5 = f"{M}\\Cbottom.png", f"{M}\\Pedestrain.png", f"{M}\\Block.png", f"{M}\\Zhorizontal.png", f"{M}\\TLyellow.png"
RD1, RD2  = f"{M}\\Rvertical.png", f"{M}\\Rcrossroads.png"
TL_RED, TL_YELLOW, TL_GREEN = f"{M}\\TLred.png", f"{M}\\TLyellow.png", f"{M}\\TLgreen.png"
TL_CYCLE = [TL_RED, TL_YELLOW, TL_GREEN]
TL_CMD   = {TL_RED: b"R", TL_YELLOW: b"Y", TL_GREEN: b"G"}
ROADS    = {RD1, RD2}
OBJECTS  = {IMG1: "Машина", IMG2: "Пешеход", IMG3: "Знак", IMG4: "Зебра",
            IMG5: "Светофор", RD1: "Дорога", RD2: "Перекрёсток"}

CELL, COLS, ROWS = 36, 21, 21

PLACE_IMGS = [IMG1, IMG2, IMG3, IMG4, IMG5, RD1, RD2]
PLACE_NAMES = ["Машина", "Пешеход", "Знак", "Зебра", "Светофор", "Дорога", "Перекресток",]

FREE = {IMG2}
ROT = {IMG1, IMG2, IMG4, IMG5, RD1, RD2}
CYCLES = {
    IMG1: [IMG1, f"{M}\\BCvertical.png", f"{M}\\GCicon.png"],
    IMG3: [IMG3, f"{M}\\Stop.png", f"{M}\\Start.png"],
    IMG5: [IMG5, f"{M}\\TLred.png", f"{M}\\TLgreen.png"]
}
def init_db():
    con = sqlite3.connect(DB_FILE)
    con.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, event TEXT)")
    con.commit(); con.close()

def log(event):
    con = sqlite3.connect(DB_FILE)
    con.execute("INSERT INTO events(time,event) VALUES(?,?)", (time.strftime("%Y-%m-%d %H:%M:%S"), event))
    con.commit(); con.close()

def get_px(path, rot = 0):
    p = QPixmap(path)
    return p.transformed(QTransform().rotate(rot)) if rot and not p.isNull() else p
class Arduino:
    def __init__(self, port):
        self._s = None
        if HAS_SERIAL and port:
            try: self._s = serial.Serial(port, 9600, timeout=1); time.sleep(2)
            except Exception as e: print(f"Arduino: {e}")
    
    def send_tl(self, path):
        if cmd := TL_CMD.get(path):
            try: self._s and self._s.write(cmd) and self._s.flush()
            except Exception as e: print(f"Serial: {e}")

ARD = None

class Grid(QWidget):
    def __init__(self, side):
        super().__init__()
        self.setFixedSize(COLS * CELL, ROWS * CELL)
        self.side = side; self.roads, self.objs = {}, {}; self.mode = self.sel = None
        self.setMouseTracking(True)

    def mouseMoveEvent(self, e):
        x, y = int(e.position().x()//CELL), int(e.position().y()//CELL)
        self.setToolTip(f"x:{x} y:{y}" if 0 <= x < COLS and 0 <= y < ROWS else "")

    def paintEvent(self, _):
        p = QPainter(self); p.fillRect(self.rect(), QColor(235, 235, 235))
        for layer in (self.roads, self.objs):
            for (x, y), o in layer.items():
                img = get_px(o["path"], o["rot"])
                if not img.isNull(): p.drawPixmap(x * CELL, y * CELL, CELL, CELL, img)
        p.setPen(QPen(QColor(0, 0, 0, 50)))
        for i in range(COLS + 1): p.drawLine(i * CELL, 0, i * CELL, ROWS * CELL)
        for i in range(ROWS + 1): p.drawLine(0, i * CELL, COLS * CELL, i * CELL)
    
    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton: return
        x, y = int(e.position().x()//CELL), int(e.position().y()//CELL)
        if not (0 <= x < COLS and 0 <= y < ROWS): return
        c = (x, y)
        if self.mode =='place' and self.sel:
            if self.sel in (RD1, RD2): self.roads[c] = {"path": self.sel,
                                                        "base": self.sel,
                                                         "rot": 0 }
            elif c in self.roads or self.sel in FREE: self.objs[c] = {"path": self.sel,
                                                                      "base": self.sel,
                                                                      "rot": 0,
                                                                      "speed": 0}
        else:
            o = self.objs.get(c) or self.roads.get(c)
            if o: self.side.show_props(c, o, self)
        self.update()

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"roads": {f"{k[0]}, {k[1]}": v for k, v in self.roads.items()},
                       "objs": {f"{k[0]}, {k[1]}": v for k, v in self.objs.items()}}, f, indent = 2)
            
    def load(self, path):
        try:
            with open(path, encoding="utf-8") as f: data = json.load(f)
            p = lambda d: {tuple(map(int, k.split(","))): v for k, v in d.items()}
            self.roads, self.objs = p(data.get("roads", {})), p(data.get("objs", {})); self.update()
        except Exception: pass

class Side(QWidget):
    def __init__(self):
        super().__init__()
        self.grid = None; self.ibtns = []
        self._auto_obj  = None
        self._auto_grid = None
        self._timer = QTimer(interval=3000)
        self._timer.timeout.connect(self._auto_tick)

        hb = QHBoxLayout(self); hb.setContentsMargins(6, 2, 6, 2); hb.setSpacing(4)
        self.sp = self._sec(PLACE_IMGS, PLACE_NAMES)
        self.props = QWidget(); self.pvb = QHBoxLayout(self.props)
        self.pvb.setContentsMargins(0, 0, 0, 0); self.pvb.setSpacing(4)
        for w in (self.sp, self.props): w.hide(); hb.addWidget(w)
        hb.addStretch()

    def _sec(self, paths, names):
        w = QWidget(); hb = QHBoxLayout(w); hb.setContentsMargins(0, 0, 0, 0); hb.setSpacing(4)
        for p, name in zip(paths, names):
            b = QPushButton(name); b.setFixedHeight(30); b.setCheckable(True); b.setProperty("path", p)
            b.clicked.connect(self._pick); hb.addWidget(b); self.ibtns.append(b)
        return w
    
    def _pick(self):
        s = self.sender()
        for b in self.ibtns:
            if b is not s: b.setChecked(False)
        if self.grid: self.grid.sel = s.property("path") if s.isChecked() else None

    def switch(self, place = False):
        for b in self.ibtns: b.setChecked(False)
        if self.grid: self.grid.sel = None; self.grid.mode = 'place' if place else None
        self.props.hide(); self.sp.setVisible(place)

    def show_props(self, cell, obj, grid):
        while self.pvb.count():
            w = self.pvb.takeAt(0).widget()
            if w: w.deleteLater()
        self.props.show(); base = obj["base"]
        self.pvb.addWidget(QLabel(f"<b>{os.path.basename(base)}</b>"))
        if base in ROT:
            b = QPushButton("Повернуть")
            b.clicked.connect(lambda: (obj.update(rot=(obj["rot"]+90)%360), grid.update()))
            self.pvb.addWidget(b)
        if base in CYCLES:
            b = QPushButton("Изменить тип"); c = CYCLES[base]
            def color(_, o = obj, cy = c):
                i = cy.index(o["path"]) if o["path"] in cy else 0
                o["path"] = cy[(i + 1) % len(cy)]; grid.update()
            b.clicked.connect(color); self.pvb.addWidget(b)
        b = QPushButton("Удалить"); b.setStyleSheet("color:red;")
        def dele(_, c = cell, g = grid): self._timer.stop(); g.objs.pop(c, None); g.roads.pop(c, None); g.update(); self.props.hide()
        b.clicked.connect(dele); self.pvb.addWidget(b)
        if base == IMG5:
            b = QPushButton("Ручной режим")
            def on_manual(_, o=obj, g=grid):
                idx = TL_CYCLE.index(o["path"]) if o["path"] in TL_CYCLE else 0
                o["path"] = TL_CYCLE[(idx+1) % 3]
                if ARD: ARD.send_tl(o["path"])
                log(f"Ручной: {os.path.basename(o['path'])}"); g.update()
            b.clicked.connect(on_manual); self.pvb.addWidget(b)

            ba = QPushButton("Авторежим"); ba.setCheckable(True)
            def on_auto(checked, o=obj, g=grid):
                if checked: self._auto_obj=o; self._auto_grid=g; self._timer.start(); log("Авторежим вкл")
                else: self._timer.stop(); log("Авторежим выкл")
            ba.clicked.connect(on_auto); self.pvb.addWidget(ba)

    def _auto_tick(self):
        if not self._auto_obj: return
        o = self._auto_obj
        o["path"] = TL_CYCLE[(TL_CYCLE.index(o["path"])+1) % 3] if o["path"] in TL_CYCLE else TL_CYCLE[0]
        if self._auto_grid: self._auto_grid.update()
        if ARD: ARD.send_tl(o["path"])
        log(f'Авто: {os.path.basename(o["path"])}')

    
class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Интеллектуальная Дорожная Система")
        lp = QPixmap(LOGO)
        if not lp.isNull(): self.setWindowIcon(QIcon(lp))
        self.side = Side(); self.grid = Grid(self.side); self.side.grid = self.grid

        c = QWidget(); self.setCentralWidget(c)
        root = QVBoxLayout(c); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        root.addWidget(self.grid)

        bar = QHBoxLayout(); bar.setContentsMargins(6, 6, 6, 6); bar.setSpacing(6)
        self.bp = QPushButton("Добавить объект"); self.bp.setCheckable(True)
        bs = QPushButton("Сохранить"); bl = QPushButton("Загрузить")
        self.bp.toggled.connect(lambda v: self.side.switch(place=v))
        bs.clicked.connect(lambda: (fn:= QFileDialog.getSaveFileName(self,"", "","JSON (*.json)")[0]) and self.grid.save(fn))
        bl.clicked.connect(lambda: (fn:= QFileDialog.getOpenFileName(self,"", "","JSON (*.json)")[0]) and self.grid.load(fn))
        for b in (self.bp, bs, bl):
            b.setFixedHeight(32); b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed); bar.addWidget(b)

        bottom = QVBoxLayout(); bottom.setContentsMargins(0, 0, 0, 0); bottom.setSpacing(0)
        bottom.addWidget(self.side); bottom.addLayout(bar)
        root.addLayout(bottom); self.adjustSize()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    init_db()
    ARD = Arduino(None)
    w = App(); w.show()
    QTimer.singleShot(0, lambda: (w.grid.load(MAP_FILE), w.grid.update()))
    sys.exit(app.exec())