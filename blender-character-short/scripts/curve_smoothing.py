"""Bounded fixed-end cubic NURBS fitting, independent of Blender and assets.

Lengths and displacements use the input coordinate unit. Relative bow factors
become ill-conditioned near a straight chord; bound the actual displacement.
"""
from functools import lru_cache
import math
import numpy as np


def points_array(points):
    values = np.asarray(points, dtype=float)
    if (values.ndim != 2 or values.shape[1] != 3 or not 4 <= len(values) <= 128
            or not np.isfinite(values).all()):
        raise ValueError('Finite 4..128 by 3 control coordinates required')
    return values


def knots(count):
    if type(count) is not int or not 4 <= count <= 128:
        raise ValueError('Cubic control count must be 4..128')
    return np.r_[np.zeros(4), np.arange(1, count - 3) / (count - 3), np.ones(4)]


def basis(parameters, vector, degree):
    parameters = np.atleast_1d(np.asarray(parameters, dtype=float))
    if not np.isfinite(parameters).all() or np.any(parameters < 0) or np.any(parameters > 1):
        raise ValueError('Finite parameters in [0,1] required')
    result = ((parameters[:, None] >= vector[:-1]) & (parameters[:, None] < vector[1:])).astype(float)
    result[parameters == 1, len(vector) - degree - 2] = 1.
    for order in range(1, degree + 1):
        size = len(vector) - order - 1
        left_den = vector[order:order + size] - vector[:size]
        right_den = vector[order + 1:order + size + 1] - vector[1:size + 1]
        left = np.divide(parameters[:, None] - vector[:size], left_den,
                         out=np.zeros((len(parameters), size)), where=left_den != 0)
        right = np.divide(vector[order + 1:order + size + 1] - parameters[:, None], right_den,
                          out=np.zeros((len(parameters), size)), where=right_den != 0)
        result = left * result[:, :size] + right * result[:, 1:size + 1]
    return result


def evaluate(points, parameters):
    points = points_array(points)
    result = basis(parameters, knots(len(points)), 3) @ points
    params = np.atleast_1d(parameters)
    result[params == 0], result[params == 1] = points[0], points[-1]
    return result


@lru_cache(maxsize=16)
def quadrature(count, order):
    if type(order) is not int or not 8 <= order <= 32:
        raise ValueError('Gauss order must be 8..32')
    vector = knots(count)
    abscissa, weights = np.polynomial.legendre.leggauss(order)
    spans = [(a, b) for a, b in zip(vector[:-1], vector[1:]) if b > a]
    parameters = np.concatenate([(a + b) / 2 + (b - a) / 2 * abscissa for a, b in spans])
    metric = np.concatenate([(b - a) / 2 * weights for a, b in spans])
    derivative = np.zeros((count - 1, count))
    for index in range(count - 1):
        scale = 3 / (vector[index + 4] - vector[index + 1])
        derivative[index, index:index + 2] = (-scale, scale)
    return basis(parameters, vector[1:-1], 2) @ derivative, metric


def arc_length(points, order=16):
    points = points_array(points)
    derivative, weights = quadrature(len(points), order)
    return float(weights @ np.linalg.norm(derivative @ points, axis=1))


def fit_bow(points, target_length, max_displacement, tolerance=1e-6):
    """Fit only perpendicular bow; preserve endpoints and chord projections.

    Refuse an unreachable length or an exhausted absolute displacement budget.
    No relative scaling cap is used. Every returned proposal is still subject
    to serialization/native-curve and contact verification by its caller.
    """
    points = points_array(points)
    if not all(math.isfinite(v) and v > 0 for v in (target_length, max_displacement, tolerance)):
        raise ValueError('Finite positive length, displacement and tolerance required')
    if tolerance >= target_length or max_displacement > target_length:
        raise ValueError('Tolerance and displacement must be smaller than the target length')
    chord = points[-1] - points[0]
    distance = float(np.linalg.norm(chord))
    if distance <= 1e-12 or distance > target_length + tolerance:
        raise ValueError('Target length is unreachable with fixed endpoints')
    projection = (points - points[0]) @ chord / (distance * distance)
    if np.any(np.diff(projection) < -1e-6) or projection.min() < -1e-6 or projection.max() > 1 + 1e-6:
        raise ValueError('Control projections must progress along the chord')
    base = points[0] + projection[:, None] * chord
    bow = points - base
    base[[0, -1]], bow[[0, -1]] = points[[0, -1]], 0.
    initial = arc_length(points, 24)
    if abs(initial - target_length) <= tolerance * .25:
        return points.copy(), dict(scale=1., maximum_point_shift=0., arc_length=initial)
    bow_maximum = float(np.linalg.norm(bow, axis=1).max())
    if bow_maximum <= 1e-15:
        raise ValueError('A straight source supplies no bow direction')
    low = max(0., 1 - max_displacement / bow_maximum)
    high = 1 + max_displacement / bow_maximum
    if (arc_length(base + high * bow, 24) < target_length - tolerance * .25
            or arc_length(base + low * bow, 24) > target_length + tolerance * .25):
        raise ValueError('Target length exceeds the absolute displacement budget')
    for _ in range(48):
        middle = (low + high) / 2
        if arc_length(base + middle * bow, 24) < target_length:
            low = middle
        else:
            high = middle
    scale = (low + high) / 2
    result = base + scale * bow
    result[[0, -1]] = points[[0, -1]]
    shift = float(np.linalg.norm(result - points, axis=1).max())
    length = arc_length(result, 32)
    if shift > max_displacement + 1e-12 or abs(length - target_length) > tolerance * .5:
        raise ValueError('Fitted curve exceeds displacement or true-length bounds')
    return result, dict(scale=scale, maximum_point_shift=shift, arc_length=length,
                        quadrature_24_vs_32=abs(arc_length(result, 24) - length))


def prepare_samples(sampler, times, *, target_length, max_displacement,
                    tolerance=1e-6, max_samples=16000, refinement_passes=8, guard=None):
    """Plan linear control keys and verify quarter/mid/three-quarter intervals.

    Include all original knots and required contact times. The sampler must
    evaluate the untouched source. Retain original endpoint channels when
    applying these interior proposals. This bounded sampling is not a proof of
    every real time and never establishes hand, hook or scene contact.
    """
    times = sorted(set(float(t) for t in times))
    if (not 2 <= len(times) <= max_samples <= 16000 or not all(map(math.isfinite, times))
            or not 0 <= refinement_passes <= 12):
        raise ValueError('Finite bounded time/sample/refinement budgets required')
    original, fitted, metrics = {}, {}, {}
    max_evaluations = max_samples * 4
    def sample(t):
        if t not in original:
            if len(original) >= max_evaluations:
                raise ValueError('Source evaluation budget exhausted')
            original[t] = points_array(sampler(t)).copy()
        return original[t]
    for round_index in range(refinement_passes + 1):
        if guard is not None:
            guard()
        for t in times:
            if t not in fitted:
                fitted[t], metrics[t] = fit_bow(sample(t), target_length, max_displacement, tolerance)
        additions, worst_error, worst_shift = [], 0., 0.
        for left, right in zip(times[:-1], times[1:]):
            for fraction in (.25, .5, .75):
                t = left + (right - left) * fraction
                proposal = (1 - fraction) * fitted[left] + fraction * fitted[right]
                proposal[[0, -1]] = sample(t)[[0, -1]]
                error = abs(arc_length(proposal, 24) - target_length)
                shift = float(np.linalg.norm(proposal - sample(t), axis=1).max())
                worst_error, worst_shift = max(worst_error, error), max(worst_shift, shift)
                if error > tolerance * .75 or shift > max_displacement + 1e-12:
                    additions.append(t)
        if not additions:
            return dict(times=np.array(times), points=np.stack([fitted[t] for t in times]),
                        summary=dict(key_times=len(times), source_evaluations=len(original),
                            refinement_rounds=round_index, maximum_interval_length_error=worst_error,
                            maximum_interval_point_shift=worst_shift,
                            maximum_key_point_shift=max(m['maximum_point_shift'] for m in metrics.values()),
                            maximum_bow_scale=max(m['scale'] for m in metrics.values()),
                            tolerance=tolerance, interval_fractions=[.25,.5,.75],
                            continuous_time_proof=False, contact_proof=False))
        if round_index == refinement_passes or len(times) + len(set(additions)) > max_samples:
            raise ValueError('Length tolerance cannot be met within refinement budget')
        times = sorted(set(times + additions))
