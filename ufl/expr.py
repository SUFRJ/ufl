"""This module defines the Expr class, the superclass
for all expression tree node types in UFL.

NB! A note about other operators not implemented here:

More operators (special functions) on Exprs are defined in exproperators.py,
as well as the transpose "A.T" and spatial derivative "a.dx(i)".
This is to avoid circular dependencies between Expr and its subclasses.
"""

# Copyright (C) 2008-2014 Martin Sandve Alnes
#
# This file is part of UFL.
#
# UFL is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# UFL is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with UFL. If not, see <http://www.gnu.org/licenses/>.
#
# Modified by Anders Logg, 2008

from six.moves import xrange as range

from ufl.log import warning, error


#--- The base object for all UFL expression tree nodes ---

class Expr(object):
    """Base class for all UFL expression types."""

    #: Each Expr subclass must define __slots__ or _ufl_noslots_ at the top,
    #: to freeze member variables for objects of this class and save memory
    #: by skipping the per-instance dict

    #__slots__ = ("_hash",) # uflcore version
    __slots__ = ()
    #_ufl_noslots_ = True


    # --- Type traits are added to subclasses by the ufl_type class decorator ---

    # Note: Some of these are modified after the Expr class definition
    # because Expr is not defined yet at this point.

    # This makes it possible to do type(f)._ufl_class_ and be sure you get
    # the actual UFL class instead of a subclass from another library.
    _ufl_class_ = None

    # The handler name, used to look for type handlers in a multifunction.
    _ufl_handler_name_ = "expr"

    # The integer typecode, a contiguous index different for each type.
    _ufl_typecode_ = 0

    # Number of operands, None if not applicable for abstract types.
    _ufl_num_ops_ = None

    # True if the type is abstract, False otherwise.
    _ufl_is_abstract_ = True

    # True if the type is terminal, False otherwise, None only for Expr.
    _ufl_is_terminal_ = None

    # True if the type is a shaping operation.
    _ufl_is_shaping_ = False

    # True if the type is purely scalar, having no shape or indices.
    _ufl_is_scalar_ = False


    # --- Basic object behaviour ---

    def __init__(self):
        self._hash = None

    def __del__(self):
        pass

    def __hash__(self):
        if self._hash is None:
            self._hash = self._ufl_compute_hash_()
        return self._hash


    # --- Global variables for collecting all types ---

    # A global counter of the number of typecodes assigned
    _ufl_num_typecodes_ = 1

    # A global set of all handler names added
    _ufl_all_handler_names_ = set()

    # A global array of all Expr subclasses, indexed by typecode
    _ufl_all_classes_ = []

    # A global dict mapping language_operator_name to the type it produces
    _ufl_language_operators_ = {}


    # --- Mechanism for profiling object creation and deletion ---

    # A global array of the number of initialized objects for each typecode
    _ufl_obj_init_counts_ = [0]

    # A global array of the number of deleted objects for each typecode
    _ufl_obj_del_counts_ = [0]

    # Backup of default init and del
    _ufl_regular__init__ = __init__
    _ufl_regular__del__ = __del__

    def _ufl_profiling__init__(self):
        "Replacement constructor with object counting."
        Expr._ufl_regular__init__(self)
        Expr._ufl_obj_init_counts_[self._ufl_typecode_] += 1

    def _ufl_profiling__del__(self):
        "Replacement destructor with object counting."
        Expr._ufl_regular__del__(self)
        Expr._ufl_obj_del_counts_[self._ufl_typecode_] -= 1

    @staticmethod
    def ufl_enable_profiling():
        "Turn on object counting mechanism and reset counts to zero."
        Expr.__init__ = Expr._ufl_profiling__init__
        Expr.__del__ = Expr._ufl_profiling__del__
        for i in range(len(Expr._ufl_obj_init_counts_)):
            Expr._ufl_obj_init_counts_[i] = 0
            Expr._ufl_obj_del_counts_[i] = 0

    @staticmethod
    def ufl_disable_profiling():
        "Turn off object counting mechanism. Returns object init and del counts."
        Expr.__init__ = Expr._ufl_regular__init__
        Expr.__del__ = Expr._ufl_regular__del__
        return (Expr._ufl_obj_init_counts_, Expr._ufl_obj_del_counts_)


    #=== Abstract functions that must be implemented by subclasses ===

    #--- Functions for reconstructing expression ---

    # All subclasses must implement reconstruct
    def reconstruct(self, *operands):
        "Return a new object of the same type with new operands."
        raise NotImplementedError(self.__class__.reconstruct)

    #--- Functions for expression tree traversal ---

    # All subclasses must implement operands
    def operands(self):
        "Return a sequence with all subtree nodes in expression tree."
        raise NotImplementedError(self.__class__.operands)

    #--- Functions for geometric properties of expression ---

    # All subclasses must implement domains if it is known
    def domains(self):
        # TODO: Is it better to use an external traversal algorithm for this?
        from ufl.geometry import extract_domains
        return extract_domains(self)

    # All subclasses must implement domain if it is known
    def domain(self):
        "Return the single unique domain this expression is defined on or throw an error."
        domains = self.domains()
        if len(domains) == 1:
            domain, = domains
            return domain
        elif domains:
            error("Found multiple domains, cannot return just one.")
        else:
            return None

    # All subclasses must implement cell if it is known
    def cell(self): # TODO: Deprecate this
        "Return the cell this expression is defined on."
        domain = self.domain()
        return domain.cell() if domain is not None else None

    # This function was introduced to clarify and
    # eventually reduce direct dependencies on cells.
    def geometric_dimension(self):
        "Return the geometric dimension this expression lives in."
        # TODO: Deprecate this, and use external analysis algorithm?
        for domain in self.domains():
            return domain.geometric_dimension()
        error("Cannot get geometric dimension from an expression with no domains!")

    def is_cellwise_constant(self):
        "Return whether this expression is spatially constant over each cell."
        raise NotImplementedError(self.__class__.is_cellwise_constant)

    #--- Functions for float evaluation ---

    def evaluate(self, x, mapping, component, index_values):
        """Evaluate expression at given coordinate with given values for terminals."""
        error("Symbolic evaluation of %s not available." % self._ufl_class_.__name__)

    def __float__(self):
        if self.ufl_shape != () or self.free_indices() != ():
            raise NotImplementedError(self.__class__.__float__)
        return self(()) # No known x

    #--- Functions for shape and index handling ---

    def shape(self):
        "Return the tensor shape of the expression."
        return self.ufl_shape

    def rank(self):
        "Return the tensor rank of the expression."
        return len(self.ufl_shape)

    # All subclasses that can have indices must implement free_indices
    def free_indices(self):
        "Return a tuple with the free indices (unassigned) of the expression."
        raise NotImplementedError(self.__class__.free_indices)

    # All subclasses must implement index_dimensions
    def index_dimensions(self):
        """Return a dict with the free or repeated indices in the expression
        as keys and the dimensions of those indices as values."""
        raise NotImplementedError(self.__class__.index_dimensions)

    #--- Special functions for string representations ---

    # All subclasses must implement signature_data
    def signature_data(self):
        "Return data that uniquely identifies form compiler relevant aspects of this object."
        raise NotImplementedError(self.__class__.signature_data)

    # All subclasses must implement __repr__
    def __repr__(self):
        "Return string representation this object can be reconstructed from."
        raise NotImplementedError(self.__class__.__repr__)

    # All subclasses must implement __str__
    def __str__(self):
        "Return pretty print string representation of this object."
        raise NotImplementedError(self.__class__.__str__)

    def _repr_latex_(self):
        from ufl.algorithms import ufl2latex
        return "$%s$" % ufl2latex(self)

    def _repr_png_(self):
        from IPython.lib.latextools import latex_to_png
        return latex_to_png(self._repr_latex_())

    #--- Special functions used for processing expressions ---

    def __eq__(self, other):
        """Checks whether the two expressions are represented the
        exact same way. This does not check if the expressions are
        mathematically equal or equivalent! Used by sets and dicts."""
        raise NotImplementedError(self.__class__.__eq__)

    def __bool__(self):
        "By default, all Expr are nonzero."
        return True

    def __nonzero__(self):
        "By default, all Expr are nonzero."
        return bool(self)

    def __len__(self):
        "Length of expression. Used for iteration over vector expressions."
        s = self.ufl_shape
        if len(s) == 1:
            return s[0]
        raise NotImplementedError("Cannot take length of non-vector expression.")

    def __iter__(self):
        "Iteration over vector expressions."
        for i in range(len(self)):
            yield self[i]

    def __floordiv__(self, other):
        "UFL does not support integer division."
        raise NotImplementedError(self.__class__.__floordiv__)

    def __pos__(self):
        "Unary + is a no-op."
        return self

    #def __getnewargs__(self): # TODO: Test pickle and copy with this. Must implement differently for Terminal objects though.
    #    "Used for pickle and copy operations."
    #    return self.ufl_operands


# Initializing traits here because Expr is not defined in the class declaration
Expr._ufl_class_ = Expr
Expr._ufl_all_handler_names_.add(Expr)
Expr._ufl_all_classes_.append(Expr)
