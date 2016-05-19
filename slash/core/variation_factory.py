import collections
import itertools

from .variation import Variation
from .._compat import OrderedDict, imap, izip, reduce, xrange
from ..exceptions import FixtureException
from ..utils.python import getargspec
from .fixtures.parameters import iter_parametrization_fixtures
from .fixtures.utils import nofixtures


class VariationFactory(object):

    """Helper class to produce variations, while properly naming the needed fixtures to help identifying tests
    """

    def __init__(self, fixture_store):
        super(VariationFactory, self).__init__()
        self._store = fixture_store
        self._needed_fixtures = list(fixture_store.iter_autouse_fixtures_in_namespace())
        self._name_bindings = OrderedDict()
        self._known_value_strings = collections.defaultdict(dict)

    def add_needed_fixture_id(self, fixture_id):
        self._needed_fixtures.append(self._store.get_fixture_by_id(fixture_id))

    def add_needed_fixtures_from_method(self, method):
        self._add_needed_fixtures_from_function(method, is_method=True)

    def add_needed_fixtures_from_function(self, func):
        self._add_needed_fixtures_from_function(func, is_method=False)

    def _add_needed_fixtures_from_function(self, func, is_method):

        if isinstance(func, tuple):
            namespace, func = func
        else:
            namespace = None

        if nofixtures.is_marked(func):
            return

        arg_names = getargspec(func).args[1 if is_method else 0:]

        parametrizations = {}
        for name, param in iter_parametrization_fixtures(func):
            # make sure the parametrization is in the store
            self._store.ensure_known_parametrization(param)
            parametrizations[name] = param

        for arg_name in arg_names:
            fixture = parametrizations.get(arg_name, None)
            if fixture is None:
                try:
                    fixture = self._store.get_fixture_by_name(arg_name)
                except FixtureException as e:
                    raise type(e)('Loading {0.__code__.co_filename}:{0.__name__}: {1}'.format(func, e))


            self._needed_fixtures.append(fixture)
            if namespace is not None:
                arg_name = '{0}:{1}'.format(namespace, arg_name)
            self._name_bindings[arg_name] = fixture

    def iter_variations(self):
        param_ids = list(reduce(set.union, imap(self._store.get_all_needed_fixture_ids, self._needed_fixtures), set()))
        parametrizations = [self._store.get_fixture_by_id(param_id) for param_id in param_ids]
        if not param_ids:
            yield Variation(self._store, {}, self._name_bindings.copy())
            return
        for value_indices in itertools.product(*(xrange(len(p.values)) for p in parametrizations)):
            yield self._build_variation(parametrizations, value_indices)

    def _build_variation(self, parametrizations, value_indices):
        param_value_indices = dict((p.info.id, param_index)
                              for p, param_index in izip(parametrizations, value_indices))
        return Variation(self._store, param_value_indices, self._name_bindings.copy())