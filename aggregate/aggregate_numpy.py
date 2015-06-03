import numpy as np

from .utils import (no_separate_nan_version, fill_untouched,
                    check_boolean, minimum_dtype, aliasing_numpy as aliasing)


def _sort(group_idx, a, n, fill_value, dtype=None, reversed_=False):
    if isinstance(a.dtype, np.complex):
        raise NotImplementedError("a must be real, could use np.lexsort or sort with recarray for complex.")
    if not (np.isscalar(fill_value) or len(fill_value) == 0):
        raise ValueError("fill_value must be scalar or an empty sequence")
    if reversed_:
        order_group_idx = np.argsort(group_idx + -1j * a)
    else:
        order_group_idx = np.argsort(group_idx + 1j * a)
    counts = np.bincount(group_idx, minlength=n)
    if np.ndim(a) == 0:
        a = np.full(n, a)
    ret = np.split(a[order_group_idx], np.cumsum(counts)[:-1])
    ret = np.asarray(ret, dtype=object)
    if np.isscalar(fill_value):
        fill_untouched(group_idx, ret, fill_value)
    return ret

def _rsort(group_idx, a, n, fill_value, dtype=None):
    return _sort(group_idx, a, n, fill_value, dtype=None, reversed_=True)

def _array(group_idx, a, n, fill_value, dtype=None):
    """groups a into separate arrays, keeping the order intact."""
    if not (np.isscalar(fill_value) or len(fill_value) == 0):
        raise ValueError("fill_value must be scalar or an empty sequence")
    order_group_idx = np.argsort(group_idx, kind='mergesort')
    counts = np.bincount(group_idx, minlength=n)
    ret = np.split(a[order_group_idx], np.cumsum(counts)[:-1])
    ret = np.asarray(ret, dtype=object)
    if np.isscalar(fill_value):
        fill_untouched(group_idx, ret, fill_value)
    return ret

def _sum(group_idx, a, n, fill_value, dtype=None):
    dtype = minimum_dtype(fill_value, dtype or a.dtype)
    if np.ndim(a) == 0:
        ret = np.bincount(group_idx, minlength=n).astype(dtype)
        if a != 1:
            ret *= a
    else:
        ret = np.bincount(group_idx, weights=a, minlength=n).astype(dtype)
    if fill_value != 0:
        fill_untouched(group_idx, ret, fill_value)
    return ret

def _last(group_idx, a, n, fill_value, dtype=None):
    dtype = minimum_dtype(fill_value, dtype or a.dtype)
    if fill_value == 0:
        ret = np.zeros(n, dtype=dtype)
    else:
        ret = np.full(n, fill_value, dtype=dtype)
    # repeated indexing gives last value, see:
    # the phrase "leaving behind the last value"  on this page:
    # http://wiki.scipy.org/Tentative_NumPy_Tutorial
    ret[group_idx] = a
    return ret

def _first(group_idx, a, n, fill_value, dtype=None):
    dtype = minimum_dtype(fill_value, dtype or a.dtype)
    if fill_value == 0:
        ret = np.zeros(n, dtype=dtype)
    else:
        ret = np.full(n, fill_value, dtype=dtype)
    ret[group_idx[::-1]] = a[::-1]  # same trick as _last, but in reverse
    return ret


def _prod(group_idx, a, n, fill_value, dtype=None):
    dtype = minimum_dtype(fill_value, dtype or a.dtype)
    ret = np.full(n, fill_value, dtype=dtype)
    if fill_value != 1:
        ret[group_idx] = 1  # product starts from 1
    np.multiply.at(ret, group_idx, a)
    return ret


def _all(group_idx, a, n, fill_value, dtype=bool):
    check_boolean(fill_value, name="fill_value")
    ret = np.full(n, fill_value, dtype=bool)
    if fill_value:
        pass  # already initialised to True
    else:
        ret[group_idx] = True
    ret[group_idx.compress(np.logical_not(a))] = False
    return ret

def _any(group_idx, a, n, fill_value, dtype=bool):
    check_boolean(fill_value, name="fill_value")
    ret = np.full(n, fill_value, dtype=bool)
    if fill_value:
        ret[group_idx] = False
    else:
        pass  # already initialsied to False
    ret[group_idx.compress(a)] = True
    return ret

def _min(group_idx, a, n, fill_value, dtype=None):
    dtype = minimum_dtype(fill_value, dtype or a.dtype)
    dmax = np.iinfo(a.dtype).max if issubclass(a.dtype.type, np.integer) else np.finfo(a.dtype).max
    ret = np.full(n, fill_value, dtype=dtype)
    if fill_value != dmax:
        ret[group_idx] = dmax  # min starts from maximum
    np.minimum.at(ret, group_idx, a)
    return ret

def _max(group_idx, a, n, fill_value, dtype=None):
    dtype = minimum_dtype(fill_value, dtype or a.dtype)
    dmin = np.iinfo(a.dtype).min if issubclass(a.dtype.type, np.integer) else np.finfo(a.dtype).min
    ret = np.full(n, fill_value, dtype=dtype)
    if fill_value != dmin:
        ret[group_idx] = dmin  # max starts from minimum
    np.maximum.at(ret, group_idx, a)
    return ret

def _mean(group_idx, a, n, fill_value, dtype=None):
    if np.ndim(a) == 0:
        raise ValueError("cannot take mean with scalar a")
    dtype = float if dtype is None else dtype
    counts = np.bincount(group_idx, minlength=n)
    sums = np.bincount(group_idx, weights=a, minlength=n)
    with np.errstate(divide='ignore'):
        ret = sums.astype(dtype) / counts
    if not np.isnan(fill_value):
        ret[counts == 0] = fill_value
    return ret

def _var(group_idx, a, n, fill_value, dtype=None, sqrt=False):
    if np.ndim(a) == 0:
        raise ValueError("cannot take variance with scalar a")
    dtype = float if dtype is None else dtype
    counts = np.bincount(group_idx, minlength=n)
    sums = np.bincount(group_idx, weights=a, minlength=n)
    with np.errstate(divide='ignore'):
        means = sums.astype(dtype) / counts
        ret = np.bincount(group_idx, (a - means[group_idx]) ** 2, minlength=n) / counts
    if sqrt:
        ret = np.sqrt(ret)  # this is now std not var
    if not np.isnan(fill_value):
        ret[counts == 0] = fill_value
    return ret

def _std(group_idx, a, n, fill_value, dtype=None):
    return _var(group_idx, a, n, fill_value, dtype=dtype, sqrt=True)

def _allnan(group_idx, a, n, fill_value, dtype=bool):
    return _all(group_idx, np.isnan(a), n, fill_value=fill_value, dtype=dtype)

def _anynan(group_idx, a, n, fill_value, dtype=bool):
    return _any(group_idx, np.isnan(a), n, fill_value=fill_value, dtype=dtype)

def _generic_callable(group_idx, a, n, fill_value, dtype=None, func=lambda g: g):
    """groups a by inds, and then applies foo to each group in turn, placing
    the results in an array."""
    groups = _array(group_idx, a, n, (), dtype=dtype)
    ret = np.full(n, fill_value, dtype=object)
    for ii, g in enumerate(groups):
        if np.ndim(g) == 1 and len(g) > 0:
            ret[ii] = func(g)
    return ret

_impl_dict = dict(min=_min, max=_max, sum=_sum, prod=_prod, last=_last, first=_first,
                    all=_all, any=_any, mean=_mean, std=_std, var=_var,
                    anynan=_anynan, allnan=_allnan, sort=_sort, rsort=_rsort,
                    array=_array)


def aggregate(group_idx, a, func='sum', size=None, fill_value=0, order='F', dtype=None, _impl_dict=_impl_dict):
    '''
    Aggregation similar to Matlab's `accumarray` function.
    
    See readme file at https://github.com/ml31415/accumarray for 
    full description.

    Parameters
    ----------
    group_idx : 1D or ndarray or sequence of 1D ndarrays
        The length of the 1d array(s) should be the same shape as `a`.
        This gives the "bin" (aka "group" or "index") in which to put the 
        given values, before* evaluating the aggregation function. 
        [*actually it's not really done in a separate step beforehand 
        in most cases, but you can think of it like that.]
    a : 1D ndarray or scalar
        The data to be aggregated. Note that the matlab version of this
        function accepts ndimensional inputs, but this does not.  Instead
        you must use `inds.ravel(), a.ravel()`. (Note that if your arrays 
        are `order='F'` you can use this as a kwarg to `ravel` to prevent
        excess work being done, although the two arrays must match).
    size : scalar or 1D sequence or None
        The desired shape of the output.  Note that no check is performed
        to ensure that indices of `group_idx` are within the specified size.
        If `group_idx` is a sequence of 1D arrays `size` must be a 1d sequence or None
        rather than a scalar.
    func : string or callable (i.e. function)
        The primary list is: `"sum", "min", "max", "mean", "std", "var", "prod",
        "all", "any", "first", "last", "sort", "rsort", "array", "allnan", "anynan"`.  
        All, but the last five, are also available in a nan form as: 
        `"nansum", "nanmin"...etc.`  Note that any groups with only nans will
        be considered empty and assigned `fill_value`, rather than being assinged
        `nan`. (If you want such groups to have the value `nan` you can use
        `"allnan"` to check which groups are all nan, and then set them to 
        `nan` in your output data.)
        
        For convenience a few aliases are defined (for both the nan and basic 
        versions):
         * `"min"`: `"amin"` and `"minimum"`       
         * `"max"`: `"amin"` and `"minimum"`       
         * `"prod"`: `"product"` and `"times"` and `"multiply"`    
         * `"sum"`: `"plus"` and `"add"`    
         * `"any"`: `"or"`     
         * `"all"`: `"and"`   
         * `"array"`: `"split"` and `"splice"`    
         * `"sort"`: `"sorted"` and `"asort"` and `"asorted"`     
         * `"rsort"`: `"rsorted"` and `"dsort"` and `"dsorted"`    
        
        The string matching is case-insensitive.
        
        By providing one of the recognised string inputs you will get an optimised
        function (although, as of numpy 1.9, `"min"`, `"max"` and `"prod"
        are actually not as fast as they should be, by a factor of 10x or more.)
        
        If instead of providing a string you provide a numpy function, e.g.
        `np.sum`, in most cases, this will be aliased to one of the above strings.
        If no alias is recognised, it will be treated as a generic callable function.
        
        For the case of generic callable functions, the data will be split into 
        actual groups and fed into the callable, one at a time.
        This is true even for `np.ufunc`s, which could potentially use their
        `.at` methods.  However using `.at` requires some understanding of what 
        the function is diong, e.g. logical_or should be initialised with 0s,
        but logical_and should be initialised with 1s.
        
    fill_value: scalar
        specifies the value to put in output where there was no input data,
        default is `0`, but you might want `np.nan` or some other specific
        value of your choosing.
        
    _impl_dict:
        This is for benchmarking, testing, and development only, i.e. NOT
        for everyday use!!
    
    Returns
    -------
    out : ndarray
        The aggregated results.  The dtype of the result will be float in cases
        where division occurs as part of the aggregation, otherwise the minimal
        dtype will be chosen to match `a` and the `fill_value`.
    
    Examples
    --------
    >>> from numpy import array
    >>> a = array([12.0, 3.2, -15, 88, 12.9])
    >>> group_idx = array([1,    0,    1,  4,   1  ])
    >>> aggregate(group_idx, a) # group a by group_idx and sum
    array([3.2, 9.9, 0, 88.])
    >>> aggregate(group_idx, a, size=8, func='min', fillval=np.nan)
    array([3.2, -15., nan, 88., nan, nan, nan, nan])
    >>> aggregate(test_group_idx, test_a, size=5, func=lambda x: ' + '.join(str(xx) for xx in x),fill_value='')
    ['3.2' '12.0 + -15.0 + 12.9' '' '' '88.0']
    '''


    a = np.asanyarray(a)
    group_idx = np.asanyarray(group_idx)

    # do some basic checking on a
    if not issubclass(group_idx.dtype.type, np.integer):
        raise TypeError("group_idx must be of integer type")
    if np.ndim(a) > 1:
        raise ValueError("a must be scalar or 1 dimensional, use .ravel to flatten.")

    # Do some fairly extensive checking of group_idx and a, trying to give the user
    # as much help as possible with what is wrong.
    # Also, convert ndindexing to 1d indexing
    ndim_idx = np.ndim(group_idx)
    if ndim_idx not in (1, 2):
        raise ValueError("Expected indices to have either 1 or 2 dimension.")
    elif ndim_idx == 1:
        if not (np.ndim(a) == 0 or len(a) == group_idx.shape[0]):
            raise ValueError("group_idx and a must be of the same length, or a can be scalar")
        if np.any(group_idx < 0):
            raise ValueError("Negative indices not supported.")
        if size is not None:
            if not np.isscalar(size):
                raise ValueError("Output size must be scalar or None")
            if np.any(group_idx > size - 1):
                raise ValueError("One or more indices are too large for size %d." % size)
        else:
            size = np.max(group_idx) + 1
        size_n = size
    else:  # ndim_idx == 2
        if  not (np.ndim(a) == 0 or len(a) == group_idx.shape[1]):
            raise ValueError("a has length %d, but group_idx has length %d." % (len(a), group_idx.shape[1]))
        if size is None:
            size = np.max(group_idx, axis=1) + 1
        else:
            if np.isscalar(size):
                raise ValueError("Output size must be None or 1d sequence of length %d" % group_idx.shape[0])
            if len(size) != group_idx.shape[0]:
                raise ValueError("%d sizes given, but %d output dimensions specified in index" % (len(size), group_idx.shape[0]))

        group_idx = np.ravel_multi_index(tuple(group_idx), size, order=order, mode='raise')
        size_n = np.prod(size)

    if not isinstance(func, basestring):
        if func in aliasing:
            func = aliasing[func]
        elif not callable(func):
            raise ValueError("func is neither a string nor a callable object.")

    if not isinstance(func, basestring):
        # do simple grouping and execute function in loop
        ret = _generic_callable(group_idx, a, size_n, fill_value, func=func, dtype=dtype)
    else:
        # deal with nans and find the function
        original_func = func
        func = func.lower()
        if func.startswith('nan'):
            func = func[3:]
            func = aliasing.get(func, func)
            if func in no_separate_nan_version:
                raise ValueError(original_func[3:] + " does not have a nan- version.")
            if np.ndim(a) == 0:
                raise ValueError("nan- version not supported for scalar input.")
            good = ~np.isnan(a)
            a = a[good]
            group_idx = group_idx[good]
        else:
            func = aliasing.get(func, func)
        if func not in _impl_dict:
            raise NotImplementedError(original_func + " not found in list of available functions.")
        func = _impl_dict[func]

        # run the function
        ret = func(group_idx, a, size_n, fill_value=fill_value, dtype=dtype)

    # deal with ndimensional indexing
    if ndim_idx == 2:
        ret = ret.reshape(size, order=order)

    return ret
