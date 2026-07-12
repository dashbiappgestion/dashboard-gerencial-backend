import math
import numpy as np
from scipy import stats


def ols_stats(xs, ys):
    xs = [float(x) for x in xs]
    ys = [float(y) for y in ys]
    n = len(xs)
    if n < 2:
        return 0, 0, 0, 0, 1.0
    mean_x, mean_y = sum(xs)/n, sum(ys)/n
    var_x = sum((x - mean_x)**2 for x in xs)
    cov = sum((x - mean_x)*(y - mean_y) for x, y in zip(xs, ys))
    slope = cov / var_x if var_x else 0
    intercept = mean_y - slope * mean_x
    var_y = sum((y - mean_y)**2 for y in ys)
    
    ss_res = sum((y - (intercept + slope * x))**2 for x, y in zip(xs, ys))
    var_res = ss_res / (n - 2) if n > 2 else (var_y if var_y > 0 else 1.0)
    se_slope = math.sqrt(var_res / var_x) if n > 2 and var_x > 0 else (abs(slope)*0.1 if slope else 0.1)
    se_intercept = se_slope * math.sqrt(sum(x**2 for x in xs)/n) if n > 2 else 0.1
    
    se_slope = max(se_slope, 1e-5)
    se_intercept = max(se_intercept, 1e-5)
    
    return slope, intercept, se_slope, se_intercept, var_res

def run_bayesian_forecast(
    xs: list[float],
    ys: list[float],
    x_star: float,
    escenario: str,
    direccion_mejora: int,
    k_optimismo: float = 1.5,
    custom_params: dict = None
):

    if not xs or not ys:
        return None

    slope_ols, intercept_ols, se_slope, se_intercept, var_res = ols_stats(xs, ys)
    n = len(xs)

    if escenario == "real":
        return None

    m0_0 = intercept_ols
    v0_00 = se_intercept**2

    if escenario == "positivista":
        m0_1 = slope_ols + direccion_mejora * k_optimismo * se_slope
        v0_11 = se_slope**2
    elif escenario == "pesimista":
        m0_1 = slope_ols - direccion_mejora * k_optimismo * se_slope
        v0_11 = se_slope**2
    elif escenario == "personalizado" and custom_params:
        m0_1 = custom_params.get("tasa_cambio", slope_ols)
        confianza = custom_params.get("confianza", "media")
        if confianza == "alta":
            v0_11 = (se_slope**2) * 0.1
        elif confianza == "baja":
            v0_11 = (se_slope**2) * 10.0
        else:
            v0_11 = se_slope**2
    else:
        m0_1 = slope_ols
        v0_11 = se_slope**2

    m0 = np.array([m0_0, m0_1])
    V0 = np.array([[v0_00, 0], [0, v0_11]])
    V0_inv = np.linalg.inv(V0)

    X = np.column_stack((np.ones(n), np.array(xs, dtype=float)))
    y = np.array(ys, dtype=float)

    Vn_inv = V0_inv + X.T @ X
    Vn = np.linalg.inv(Vn_inv)

    mn = Vn @ (V0_inv @ m0 + X.T @ y)

    a0 = 0.01
    b0 = 0.01

    an = a0 + n / 2
    bn_val = b0 + 0.5 * (y.T @ y + m0.T @ V0_inv @ m0 - mn.T @ Vn_inv @ mn)
    bn = max(1e-10, bn_val)

    x_star_vec = np.array([1.0, x_star])
    loc = x_star_vec.T @ mn
    scale_sq = (bn / an) * (1 + x_star_vec.T @ Vn @ x_star_vec)
    scale = math.sqrt(max(0, scale_sq))
    df = 2 * an

    t_val = stats.t.ppf(0.95, df)
    margin = t_val * scale

    def safe_float(v):
        return float(v) if not math.isnan(v) else 0.0

    return {
        "punto_medio": safe_float(loc),
        "intervalo_inferior": safe_float(loc - margin),
        "intervalo_superior": safe_float(loc + margin),
        "n_datos_usados": n,
        "advertencia": "Pocos datos para una predicción confiable." if n < 3 else None
    }
