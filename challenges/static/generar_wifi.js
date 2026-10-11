"use strict";
/*
 * Genera los archivos ESTÁTICOS de los 8 retos Wi-Fi (un .pcap + wordlist por
 * reto, iguales para todos los jugadores) usando el generador del prototipo
 * `wispr_terminal_professional`, y escribe la flag real de cada uno en
 * challenges/catalog/catalog.json.
 *
 * SOLUCIÓN TEMPORAL (decidida el 11 oct): sirve para que los 10 retos se
 * puedan jugar ya (demo de EXPOTEC), pero todos los jugadores reciben el MISMO
 * archivo y por lo tanto la misma flag — se la pueden pasar entre ellos. El
 * reemplazo previsto es portar el generador a Python y crear un archivo por
 * jugador (`challenge_instances`); ver CLAUDE.md, punto 7b del plan.
 *
 * Uso (desde la raíz del repo; requiere Node, solo en la máquina que genera —
 * el backend NO necesita Node, solo sirve los archivos ya generados):
 *   node challenges/static/generar_wifi.js /ruta/a/wispr_terminal_professional
 * Después: `python -m app.db.seed_challenges` (desde backend/) para cargar las
 * flags nuevas en la base de datos.
 *
 * Es determinista (semilla fija): correrlo de nuevo produce exactamente los
 * mismos archivos y flags.
 */
const fs = require("fs");
const path = require("path");

const prototypeDir = path.resolve(process.argv[2] || "../wispr_terminal_professional");
const { materializeInstance } = require(path.join(prototypeDir, "challenge-instances.js"));

const STATIC_DIR = __dirname;
const CATALOG_FILE = path.join(__dirname, "..", "catalog", "catalog.json");
const SEED = "wispr-static-v1"; // no es secreto: las flags quedan igual en catalog.json

const catalog = JSON.parse(fs.readFileSync(CATALOG_FILE, "utf8"));
let count = 0;
for (const challenge of catalog.challenges) {
  if (!challenge.kind) continue; // solo los retos Wi-Fi del prototipo (los del pipeline no tienen `kind`)
  const instance = materializeInstance({
    player: "wispr-static", challengeId: challenge.id, baseFlag: challenge.flag,
    fileName: challenge.files[0].name, category: challenge.category,
    difficulty: challenge.difficulty, kind: challenge.kind, seedSecret: SEED
  });
  // Comprobación: el propio generador resuelve el archivo y debe llegar a la flag.
  if (instance._solve() !== instance.flag) throw new Error(`${challenge.id}: el archivo no se resuelve a su flag.`);

  const dir = path.join(STATIC_DIR, challenge.id);
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  const files = [];
  for (const file of instance.files) {
    // Nombre estable (sin el sufijo aleatorio del prototipo): el .pcap conserva
    // el nombre del catálogo; el diccionario siempre es wordlist.txt.
    const name = file.type === "pcap" ? challenge.files[0].name : file.name;
    fs.writeFileSync(path.join(dir, name), Buffer.isBuffer(file.content) ? file.content : Buffer.from(String(file.content), "utf8"));
    files.push({ name, type: file.type, desc: file.type === "pcap" ? challenge.files[0].desc : (file.desc || "Diccionario para el ataque") });
  }
  challenge.flag = instance.flag;
  challenge.files = files;
  count += 1;
  console.log(`${challenge.id}: ${files.map(f => f.name).join(", ")}`);
}
fs.writeFileSync(CATALOG_FILE, JSON.stringify(catalog, null, 2) + "\n", "utf8");
console.log(`${count} retos Wi-Fi generados en challenges/static/ y catalog.json actualizado.`);
