from __future__ import division, print_function, absolute_import

from numpy.testing import assert_equal, assert_raises

import time
import nose
import ctypes
import threading
from scipy._lib import _test_ccallback, _test_ccallback_cython

try:
    import cffi
    HAVE_CFFI = True
except ImportError:
    HAVE_CFFI = False


ERROR_VALUE = 2.0


def callback_python(a, user_data=None):
    if a == ERROR_VALUE:
        raise ValueError("bad value")

    if user_data is None:
        return a + 1
    else:
        return a + user_data


def test_callbacks():
    callers = {
        'simple': _test_ccallback.call_simple,
        'nodata': _test_ccallback.call_nodata,
        'nonlocal': _test_ccallback.call_nonlocal
    }

    def _get_cffi_func(base, signature):
        if not HAVE_CFFI:
            raise nose.SkipTest("cffi not installed")

        # Get function address
        voidp = ctypes.cast(base, ctypes.c_void_p)
        address = voidp.value

        # Create corresponding cffi handle
        ffi = cffi.FFI()
        func = ffi.cast(signature, address)
        return func

    # These functions have signatures known to the callers
    funcs = {
        'python': lambda: callback_python,
        'capsule': lambda: _test_ccallback.get_plus1_capsule(),
        'cython': lambda: (_test_ccallback_cython, "plus1_cython"),
        'ctypes': lambda: _test_ccallback_cython.plus1_ctypes,
        'cffi': lambda: _get_cffi_func(_test_ccallback_cython.plus1_ctypes,
                                       'double (*)(double, int *, void *)'),
        'capsule_b': lambda: _test_ccallback.get_plus1b_capsule(),
        'cython_b': lambda: (_test_ccallback_cython, "plus1b_cython"),
        'ctypes_b': lambda: _test_ccallback_cython.plus1b_ctypes,
        'cffi_b': lambda: _get_cffi_func(_test_ccallback_cython.plus1b_ctypes,
                                         'double (*)(double, double, int *, void *)'),
    }

    # These functions have signatures the callers don't know
    bad_funcs = {
        'capsule_bc': lambda: _test_ccallback.get_plus1bc_capsule(),
        'cython_bc': lambda: (_test_ccallback_cython, "plus1bc_cython"),
        'ctypes_bc': lambda: _test_ccallback_cython.plus1bc_ctypes,
        'cffi_bc': lambda: _get_cffi_func(_test_ccallback_cython.plus1bc_ctypes,
                                          'double (*)(double, double, double, int *, void *)'),
    }

    def check(caller, func):
        caller = callers[caller]
        func = funcs[func]()

        # Test basic call
        assert_equal(caller(func, 1.0), 2.0)

        # Test 'bad' value resulting to an error
        assert_raises(ValueError, caller, func, ERROR_VALUE)

        # Test passing in user_data
        if isinstance(func, tuple):
            func2 = func + (2.0,)
        else:
            func2 = (func, 2.0)
        assert_equal(caller(func2, 1.0), 3.0)

    def check_bad(caller, func):
        caller = callers[caller]
        func = bad_funcs[func]()

        # Test that basic call fails
        assert_raises(ValueError, caller, func, 1.0)

        # Test that passing in user_data also fails
        if isinstance(func, tuple):
            func2 = func + (2.0,)
        else:
            func2 = (func, 2.0)
        assert_raises(ValueError, caller, func2, 1.0)

    for caller in callers.keys():
        for func in funcs.keys():
            yield check, caller, func

        for func in bad_funcs.keys():
            yield check_bad, caller, func


def test_threadsafety():
    def callback(a, caller):
        if a <= 0:
            return 1
        else:
            res = caller((callback, caller), a - 1)
            return 2*res

    callers = {
        'simple': _test_ccallback.call_simple,
        'nodata': _test_ccallback.call_nodata,
        'nonlocal': _test_ccallback.call_nonlocal
    }

    def check(caller):
        caller = callers[caller]

        results = []

        count = 10

        def run():
            time.sleep(0.01)
            r = caller((callback, caller), count)
            results.append(r)

        threads = [threading.Thread(target=run) for j in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert_equal(results, [2.0**count]*len(threads))

    for caller in callers.keys():
        yield check, caller
