"""Entrena el clasificador de Cenzi y guarda el artefacto del modelo.

Pasos:
1. Parte el dataset por frase base (GroupShuffleSplit): entrenamiento 60 %,
   validación 20 %, prueba 20 %. Ninguna frase base se repite entre conjuntos.
2. Entrena TF-IDF (palabras + caracteres) + regresión logística.
3. Elige el umbral de confianza en validación: el menor umbral cuyo acierto en
   lo respondido sea >= 90 %.
4. Reentrena con entrenamiento + validación; ese es el modelo que se despliega.
   El conjunto de prueba nunca se usa para entrenar ni para elegir el umbral.
5. Guarda models/cenzi_model.joblib, models/metricas.json y
   models/conjunto_prueba.csv (para validar el contenedor contra datos no vistos).

Uso:
    python scripts/entrenar.py
"""
from __future__ import annotations

import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import FeatureUnion, Pipeline

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "data" / "consultas_cenzi.csv"
RESPUESTAS = RAIZ / "data" / "respuestas_aprobadas_cenzi.csv"
SALIDA = RAIZ / "models"
SEMILLA = 42
META_ACIERTO = 0.90
VERSION_MODELO = "1.0.0"


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def construir_pipeline() -> Pipeline:
    caracteristicas = FeatureUnion([
        ("palabras", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), strip_accents="unicode",
                                     lowercase=True, sublinear_tf=True, min_df=1)),
        ("caracteres", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), strip_accents="unicode",
                                       lowercase=True, sublinear_tf=True, min_df=2)),
    ])
    return Pipeline([
        ("tfidf", caracteristicas),
        ("clf", LogisticRegression(C=10.0, max_iter=3000, random_state=SEMILLA)),
    ])


def cobertura_y_acierto(proba: np.ndarray, y_pred: np.ndarray, y_true: np.ndarray, umbral: float):
    responde = proba.max(axis=1) >= umbral
    cobertura = float(responde.mean())
    acierto = float((y_pred[responde] == y_true[responde]).mean()) if responde.any() else float("nan")
    error_total = float(((y_pred != y_true) & responde).mean())
    return cobertura, acierto, error_total


def elegir_umbral(proba, y_pred, y_true) -> tuple[float, list[dict]]:
    curva = []
    elegido = None
    for u in np.round(np.arange(0.10, 0.96, 0.01), 2):
        cob, acc, err = cobertura_y_acierto(proba, y_pred, y_true, u)
        curva.append({"umbral": float(u), "cobertura": cob, "acierto": acc, "error_total": err})
        if elegido is None and not np.isnan(acc) and acc >= META_ACIERTO:
            elegido = float(u)
    return (elegido if elegido is not None else 0.95), curva


def main() -> None:
    filas = leer_csv(DATOS)
    respuestas = {r["intencion"]: r for r in leer_csv(RESPUESTAS)}
    X = np.array([f["texto"] for f in filas])
    y = np.array([f["intencion"] for f in filas])
    g = np.array([f["frase_base"] for f in filas])

    gss = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=SEMILLA)
    idx_tv, idx_te = next(gss.split(X, y, g))
    gss2 = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=SEMILLA)
    sub_tr, sub_va = next(gss2.split(X[idx_tv], y[idx_tv], g[idx_tv]))
    idx_tr, idx_va = idx_tv[sub_tr], idx_tv[sub_va]
    assert not (set(g[idx_tr]) & set(g[idx_te])) and not (set(g[idx_va]) & set(g[idx_te]))

    modelo = construir_pipeline().fit(X[idx_tr], y[idx_tr])
    proba_va = modelo.predict_proba(X[idx_va])
    pred_va = modelo.classes_[proba_va.argmax(axis=1)]
    umbral, curva = elegir_umbral(proba_va, pred_va, y[idx_va])

    # Evaluación en prueba con el modelo entrenado sólo con entrenamiento + validación
    modelo_tv = construir_pipeline().fit(X[idx_tv], y[idx_tv])
    t0 = time.perf_counter()
    proba_te = modelo_tv.predict_proba(X[idx_te])
    ms_por_consulta = (time.perf_counter() - t0) * 1000 / len(idx_te)
    pred_te = modelo_tv.classes_[proba_te.argmax(axis=1)]
    cob, acc, err = cobertura_y_acierto(proba_te, pred_te, y[idx_te], umbral)

    # Escalamiento seguro: quejas y aclaraciones que llegan a una persona
    acciones_reales = np.array([respuestas[i]["accion"] for i in y[idx_te]])
    responde = proba_te.max(axis=1) >= umbral
    escala_pred = ~responde | np.isin(pred_te, [k for k, v in respuestas.items() if v["accion"] == "escalar"])
    sensibles = acciones_reales == "escalar"
    sensibles_escalados = float(escala_pred[sensibles].mean())

    metricas = {
        "version_modelo": VERSION_MODELO,
        "entrenado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scikit_learn": sklearn.__version__,
        "semilla": SEMILLA,
        "n_total": int(len(X)),
        "n_entrenamiento": int(len(idx_tr)), "n_validacion": int(len(idx_va)), "n_prueba": int(len(idx_te)),
        "umbral_confianza": umbral,
        "prueba": {
            "accuracy": float(accuracy_score(y[idx_te], pred_te)),
            "f1_macro": float(f1_score(y[idx_te], pred_te, average="macro")),
            "cobertura": cob, "acierto_respondidas": acc, "error_total": err,
            "quejas_aclaraciones_escaladas": sensibles_escalados,
            "ms_por_consulta_lote": ms_por_consulta,
        },
        "reporte_por_clase": classification_report(y[idx_te], pred_te, output_dict=True, zero_division=0),
        "clases": modelo_tv.classes_.tolist(),
        "matriz_confusion": confusion_matrix(y[idx_te], pred_te, labels=modelo_tv.classes_).tolist(),
        "curva_umbral_validacion": curva,
    }

    # Artefacto desplegado: el modelo entrenado con entrenamiento + validación
    SALIDA.mkdir(parents=True, exist_ok=True)
    with (SALIDA / "conjunto_prueba.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "texto", "intencion", "accion", "frase_base"])
        w.writeheader()
        w.writerows(filas[i] for i in idx_te)
    joblib.dump({
        "pipeline": modelo_tv,
        "umbral": umbral,
        "respuestas": respuestas,
        "version": VERSION_MODELO,
        "metricas_prueba": metricas["prueba"],
    }, SALIDA / "cenzi_model.joblib")
    (SALIDA / "metricas.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=2), encoding="utf-8")

    p = metricas["prueba"]
    print(f"Datos: {len(X)} | train {len(idx_tr)} · val {len(idx_va)} · test {len(idx_te)}")
    print(f"Umbral elegido en validación: {umbral:.2f}")
    print(f"Prueba -> accuracy {p['accuracy']:.3f} | F1 macro {p['f1_macro']:.3f} | cobertura {cob:.1%} "
          f"| acierto respondidas {acc:.1%} | error total {err:.1%} | quejas/aclaraciones escaladas {sensibles_escalados:.1%}")
    print(f"Modelo guardado en {SALIDA / 'cenzi_model.joblib'}")


if __name__ == "__main__":
    main()
