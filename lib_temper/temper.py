# collection of functions for dealing with regular temperaments

from . import olll
from fractions import Fraction
import numpy as np

# from math import gcd
# from primes import primes
from itertools import combinations
from . import diophantine

from .subgroup import *
from .optimize import *
from .combo import comboBySum


# Find the hermite normal form of M
def hnf(M, remove_zeros=False, transformation=False):
    assert M.ndim == 2

    solution = diophantine.lllhermite(M.astype(np.int64))

    res = np.array(solution[0]).astype(np.int64)

    unimod = np.array(solution[1]).astype(np.int64)

    if remove_zeros:
        idx = np.argwhere(np.all(res[:] == 0, axis=1))
        res = np.delete(res, idx, axis=0)

    if transformation:
        return res, unimod
    else:
        return res


# Find the left kernel (nullspace) of M.
# Adjoin an identity block matrix and solve for HNF.
# This is equivalent to the highschool maths method,
# but using HNF instead of Gaussian elimination.
def kernel(M):
    assert M.ndim == 2
    r, d = M.shape
    n = d - r

    M = np.vstack([M, np.eye(d, dtype=np.int64)])
    K = hnf(M.T).T[r::, r::]

    return K


# Find the right kernel (nullspace) of M
def cokernel(M):
    assert M.ndim == 2
    return kernel(M.T).T


# LLL reduction
# Tries to find the smallest basis vectors in some lattice
# M: Map
# W: Weight matrix (metric)
def LLL(M, W):
    res = olll.reduction(np.copy(M).T, delta=0.99, W=W).T

    # sort them by complexity
    # actually, this might be redundant.
    c_list = list(res.T)
    c_list.sort(key=lambda c: np.dot(c, W @ c))

    return np.array(c_list).T


# Flips M along diagonal
def antitranspose(M):
    return np.flipud(np.fliplr((M.T)))


# Finds the Hermite normal form and 'defactors' it.
# Defactoring is also known as saturation.
# This removes torsion from the map.
# Algorithm as described by:
#
# Clément Pernet and William Stein.
# Fast Computation of HNF of Random Integer Matrices.
# Journal of Number Theory.
# https://doi.org/10.1016/j.jnt.2010.01.017
# See section 8.
def defactored_hnf(M):
    r, d = M.shape

    S = np.linalg.inv(hnf(M.T)[:r].T)

    assert np.allclose(S @ M, np.round(S @ M))

    D = np.round(S @ M).astype(np.int64)

    return hnf(D)


# exact integer determinant using Bareiss algorithm
# modified slightly from:
## https://stackoverflow.com/questions/66192894/precise-determinant-of-integer-nxn-matrix
def integer_det(M):
    M = np.copy(M)  # make a copy to keep original M unmodified

    N, sign, prev = len(M), 1, 1
    for i in range(N - 1):
        if M[i, i] == 0:  # swap with another row having nonzero i's elem
            swapto = next((j for j in range(i + 1, N) if M[j, i] != 0), None)
            if swapto is None:
                return 0  # all M[*][i] are zero => zero determinant
            ## swap rows
            M[[i, swapto]] = M[[swapto, i]]
            sign *= -1
        for j in range(i + 1, N):
            for k in range(i + 1, N):
                assert (M[j, k] * M[i, i] - M[j, i] * M[i, k]) % prev == 0
                M[j, k] = (M[j, k] * M[i, i] - M[j, i] * M[i, k]) // prev
        prev = M[i, i]
    return sign * M[-1, -1]


# Order of factorization.
# For a saturated basis this is 1.
def factor_order(M):
    r, d = M.shape
    return integer_det(hnf(M.T)[:r].T)


# Canonical maps
# This is just the defactored HNF,
# but for comma bases we do the antitranspose sandwich.
def canonical(M):
    assert M.ndim == 2
    r, d = M.shape
    if r > d:
        # comma basis
        return antitranspose(defactored_hnf(antitranspose(M)))
    else:
        # mapping
        return defactored_hnf(M)


# Solve AX = B in the integers
# for the method used, see https://github.com/tclose/Diophantine/blob/master/algorithm.pdf
def solve_diophantine(A, B):
    B = np.atleast_2d(B)
    assert A.shape[0] == B.shape[0]
    aug = np.block(
        [
            [A.T, np.zeros((A.shape[1], B.shape[1]), dtype=np.int64)],
            [B.T, np.eye(B.shape[1], dtype=np.int64)],
        ]
    )

    r, d = A.shape

    nullity = d - r

    # somehow we can solve the system even if the nullity is -1
    # aka the kernel is trivial
    # should double check when this actually works
    if nullity <= 0:
        nullity = 0

    H, U = hnf(aug, transformation=True)

    p2 = U.shape[0] - nullity
    p1 = p2 - B.shape[1]

    sol = -U[p1:p2, : A.shape[1]].T

    # Check that the solution actually works.
    # Probably the easiest way to guarantee this routine works correctly.
    assert np.all(A @ sol == B), "Could not solve system"

    return sol


# Find a preimage of M
# Amounts to solving MX = I
def preimage(M):
    gens = []

    rank = M.shape[0]

    gens = solve_diophantine(M, np.eye(rank, dtype=np.int64))

    return gens


# Simplify Intervals wrt Comma basis with some Weight matrix.
# The comma basis should be in reduced LLL form for this to work properly.
def simplify(I, C, W):
    intervals = I.T
    commas = C.T

    for i in range(len(intervals)):
        v = intervals[i]
        p_best = np.dot(v, W @ v)

        cont = True
        while cont:
            cont = False
            for c in commas:
                new = v - c
                p_new = np.dot(new, W @ new)
                if p_new < p_best:
                    v = new
                    p_best = p_new
                    cont = True
                else:
                    new = v + c
                    p_new = np.dot(new, W @ new)
                    if p_new < p_best:
                        v = new
                        p_best = p_new
                        cont = True
        intervals[i] = v

    return intervals.T


# Patent n-edo map
# Just crudely rounds all the log primes, multiplied by n
def patent_map(t, subgroup):
    logs = log_subgroup(subgroup)

    t = t / logs[0]  # fix equave

    # floor(x+0.5) rounds more predictably (downwards on .5)
    M = np.floor(t * logs + 0.5).astype(np.int64)
    return np.atleast_2d(M)


# Search for patent edo maps that are consistent with T up to some limit
def find_edos_patent(T, subgroup):
    assert T.ndim == 2
    r, d = T.shape
    # T = hnf(T)
    c = kernel(T)

    octave_div = T[0, 0]
    # print("octave mult:", octave_div)
    # search_range = (4.5, 665.5)

    m_list = []

    if r == 1:
        return

    seen = set()
    count = 0
    count2 = 0
    for k in range(666):
        m1 = patent_map(k, subgroup)
        # print(m1[0,0])
        if m1[0, 0] % octave_div == 0:  # skip non multiples of the octave division
            count2 += 1
            if count2 > 8000:
                break
            # if it tempers out all commas
            if np.all(m1 @ c == 0):
                # if it is not contorted
                if np.gcd.reduce(m1.flatten().tolist()) == 1:
                    badness = temp_measures((m1, subgroup))[0]
                    m_list.append((np.copy(m1), badness))

                    # only count distinct octave divisions
                    if m1[0][0] not in seen:
                        seen.add(m1[0][0])
                        count += 1
                        if count > r + 10:  # rank + 10 should be enough
                            break

    print("list count: ", len(m_list))
    print("nr checked: ", count2)

    # sort by badness
    m_list.sort(key=lambda l: l[1])

    # filter so each edo only shows up once (first on the list)
    r_list = []
    seen = set()
    for m in m_list:
        if m[0][0][0] not in seen:
            r_list.append(m)
            seen.add(m[0][0][0])

    return r_list


# Search for edo maps (GPVs) that are consistent with T up to some limit
def find_edos(T, subgroup):
    assert T.ndim == 2
    r, d = T.shape
    # T = hnf(T)
    c = kernel(T)

    octave_div = T[0, 0]
    # print("octave mult:", octave_div)
    search_range = (4.5, 1999.5)

    m_list = []

    if r == 1:
        return

    seen = set()
    count = 0
    count2 = 0
    for m1, b1 in Pmaps(search_range, subgroup):
        if m1[0, 0] % octave_div == 0:  # skip non multiples of the octave division
            count2 += 1
            if count2 > 8000:
                break
            # if it tempers out all commas
            if np.all(m1 @ c == 0):
                # if it is not contorted
                if np.gcd.reduce(m1.flatten().tolist()) == 1:
                    badness = temp_measures((m1, subgroup))[0]

                    m_list.append((np.copy(m1), badness))

                    # only count distinct octave divisions
                    if m1[0][0] not in seen:
                        seen.add(m1[0][0])
                        count += 1
                        if count > r + 25:  # rank + 25 should be enough
                            break

    print("list count: ", len(m_list))
    print("nr checked: ", count2)

    # sort by badness
    m_list.sort(key=lambda l: l[1])

    # filter so each edo only shows up once (first on the list)
    r_list = []
    seen = set()
    for m in m_list:
        if m[0][0][0] not in seen:
            r_list.append(m)
            seen.add(m[0][0][0])

    # return top 12+rank edos
    return r_list[: (r + 12)]


# Select <rank> edos that, when joined together, are equivalent to the temperament
def find_join(T, subgroup, m_list):
    assert T.ndim == 2
    r, d = T.shape
    # T = hnf(T)

    count = 0
    for combo in comboBySum(r, 0, len(m_list) - 1):
        # print(combo, flush=True)
        m_new = np.vstack([m_list[i][0] for i in combo])
        m_hnf = hnf(m_new)

        # print(m_hnf)
        count += 1

        if np.all(m_hnf == T):
            print("number of combos checked: " + str(count))
            return [m for m in m_new]

        if count > 500:
            break
    print("FAILED. number of combos checked: " + str(count))


# Iterator for general edo maps (GPVs)
class Pmaps:
    def __init__(self, bounds, subgroup):
        self.stop = bounds[1]
        self.logS = log_subgroup(subgroup)
        # assert np.all(self.logS >= 1)

        start = bounds[0]

        self.cmap = patent_map(start, subgroup)

        self.first = True

    def __iter__(self):
        return self

    def __next__(self):
        if not self.first:
            incr = np.argmin(self.ubounds)
            self.cmap[0, incr] += 1

        self.first = False

        self.lbounds = (self.cmap - 0.5) / self.logS
        self.ubounds = (self.cmap + 0.5) / self.logS

        lb = np.max(self.lbounds)
        ub = np.min(self.ubounds)

        # stop when new lower bound hits end of interval
        if lb >= self.stop:
            raise StopIteration

        ind = (lb + ub) / 2.0
        assert np.all(self.cmap == np.round(ind * self.logS).astype(np.int64))

        return self.cmap, (lb, ub)


# Find the error of a temperament
# Which here is taken as the tenney-weighted MSE
def temp_error(temp):
    M, S = temp
    r, d = M.shape

    j = log_subgroup(S)
    W = np.diag(1.0 / j)

    sol, e = lstsq(temp, weight="tenney")

    # Breed
    err = np.sqrt(np.average((e @ W) ** 2))

    # Smith
    # err = np.sqrt(np.sum((e @ W)**2) * (r + 1) / (d-r) )

    return err


# Complexity of a temperament.
# Here we take the 'simple' definition (i.e. don't try to adjust for rank or dimension).
# 1. Find the gram matrix of the temperament with tenney metric.
# 2. Calculate the determinant.
#    This is the volume of the hyperparallellepid spanned by the basis.
# 3. Take the square root.
def temp_complexity(temp):
    M, S = temp
    r, d = M.shape

    j = log_subgroup(S)
    W = np.diag(1.0 / j)

    # simple
    compl = np.sqrt(np.linalg.det((M @ W) @ (M @ W).T) / d)

    # Breed
    # compl  = np.sqrt (np.linalg.det ((M @ W) @ (M @ W).T / d))

    # Smith
    # compl = np.sqrt (np.linalg.det ((M @ W) @ (M @ W).T ) / math.comb(d,r))

    return compl


# "logflat badness"
# Combines complexity and error into a single measurement
#
# https://en.xen.wiki/w/Tenney-Euclidean_temperament_measures#TE_logflat_badness
# The reason for the exponent here can be found in:
#
# On transfer inequalities in Diophantine approximation, II
# Y. Bugeaud, M. Laurent
# Mathematische Zeitschrift volume 265, pages249–262 (2010)
#
# See corollary 2.
# Their way of counting dimensions is different:
#  rank = d + 1
#  dim = n + 1
# Then we have
#  omega = rank / (dim - rank) = dim / (dim - rank) - 1
# the -1 is because we have
# | y ∧ X | * | X | ^ omega <= C
# | X | ~ complexity
# | y ∧ X | ~ error * complexity
def temp_measures(temp):
    M, S = temp
    r, d = M.shape

    complexity = temp_complexity(temp)
    error = temp_error(temp)

    badness = error * (complexity ** (d / (d - r)))

    return badness, complexity, error
