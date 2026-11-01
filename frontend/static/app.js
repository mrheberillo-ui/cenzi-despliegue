// Frontend de Cenzi: consume la API a través del proxy /api del servidor del frontend.
const API = "/api";
const $ = (id) => document.getElementById(id);

const MOTIVOS = {
  confianza_suficiente: "Confianza suficiente",
  confianza_baja: "Confianza baja: se escala",
  intencion_requiere_persona: "La intención requiere a una persona",
  regla_queja_aclaracion: "Regla: queja o aclaración",
  datos_sensibles: "Datos sensibles detectados",
  texto_sin_contenido: "Texto sin contenido suficiente",
};

async function verificarEstado() {
  try {
    const r = await fetch("/healthz");
    const d = await r.json();
    const ok = d.backend === "listo";
    $("estado").className = "estado " + (ok ? "ok" : "mal");
    $("estado-texto").textContent = ok ? "Backend listo" : "Backend no disponible";
  } catch {
    $("estado").className = "estado mal";
    $("estado-texto").textContent = "Sin conexión";
  }
}

function mostrarError(mensaje) {
  $("error").textContent = mensaje;   // textContent: nunca se interpreta HTML
  $("error").classList.remove("oculto");
  $("resultado").classList.add("oculto");
}

function pintar(d, texto) {
  $("error").classList.add("oculto");
  $("resultado").classList.remove("oculto");
  const responde = d.accion === "responder";
  $("accion").textContent = responde ? "Respuesta automática" : "Se escala a una persona";
  $("accion").className = "etiqueta " + (responde ? "verde" : "ambar");
  $("intencion").textContent = d.intencion.replaceAll("_", " ");
  $("respuesta").textContent = d.respuesta;
  $("confianza").textContent = (d.confianza * 100).toFixed(1) + " %";
  $("umbral").textContent = (d.umbral * 100).toFixed(0) + " %";
  $("motivo").textContent = MOTIVOS[d.motivo] || d.motivo;
  $("latencia").textContent = d.latencia_ms.toFixed(1) + " ms";
  $("id-solicitud").textContent = d.id_solicitud;
  $("version").textContent = d.version_modelo;
  $("barra-confianza").style.width = (d.confianza * 100).toFixed(1) + "%";
  $("barra-confianza").className = d.confianza >= d.umbral ? "alto" : "bajo";
  $("marca-umbral").style.left = (d.umbral * 100) + "%";
  const ol = $("alternativas"); ol.replaceChildren();
  d.alternativas.forEach((a) => {
    const li = document.createElement("li");
    li.textContent = `${a.intencion.replaceAll("_", " ")} — ${(a.confianza * 100).toFixed(1)} %`;
    ol.appendChild(li);
  });
  const tr = document.createElement("tr");
  [texto, d.intencion.replaceAll("_", " "), (d.confianza * 100).toFixed(1) + " %", responde ? "Responder" : "Escalar"]
    .forEach((v) => { const td = document.createElement("td"); td.textContent = v; tr.appendChild(td); });
  $("historial").prepend(tr);
}

async function enviar(texto) {
  $("enviar").disabled = true; $("enviar").textContent = "Clasificando…";
  try {
    const r = await fetch(`${API}/v1/clasificar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texto, canal: "web" }),
    });
    const d = await r.json().catch(() => ({}));
    if (r.ok) pintar(d, texto);
    else if (r.status === 422) mostrarError("Revisa tu consulta: " + (d.detalles || []).map((e) => e.mensaje).join("; "));
    else if (r.status === 502 || r.status === 503) mostrarError(d.mensaje || "El servicio no está disponible por el momento.");
    else mostrarError(`Error inesperado (${r.status}).`);
  } catch {
    mostrarError("No hay conexión con el servidor.");
  } finally {
    $("enviar").disabled = false; $("enviar").textContent = "Enviar consulta";
    verificarEstado();
  }
}

$("formulario").addEventListener("submit", (e) => {
  e.preventDefault();
  const texto = $("texto").value.trim();
  if (!texto) { mostrarError("Escribe una consulta antes de enviar."); return; }
  enviar(texto);
});
$("texto").addEventListener("input", () => { $("contador").textContent = `${$("texto").value.length} / 500`; });
document.querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => {
  $("texto").value = b.textContent; $("contador").textContent = `${b.textContent.length} / 500`; enviar(b.textContent);
}));
verificarEstado();
setInterval(verificarEstado, 15000);
