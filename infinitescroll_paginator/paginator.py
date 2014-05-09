from django.core.exceptions import ObjectDoesNotExist

from tastypie.paginator import Paginator


class NoTotalCountPaginator(Paginator):
    """
    Original paginator from tastypie but removing total_count query
    to improve perfomance

    """

    def get_count(self):
        """
            Just avoid calling count()
        """
        return -1

    def page(self):
        """
            total_count in meta isn't needed
        """
        output = super(NoTotalCountPaginator, self).page()
        del output['meta']['total_count']

        return output


class InfiniteScrollPaginator(NoTotalCountPaginator):

    _cached_slice = None

    def __init__(self, request_data, objects, resource_uri=None, limit=None,
                 offset=0, max_limit=1000, collection_name='objects',
                 order_by=None):
        super(InfiniteScrollPaginator, self).__init__(
            request_data=request_data,
            objects=objects,
            resource_uri=resource_uri,
            limit=limit,
            offset=offset,
            max_limit=max_limit,
            collection_name=collection_name)

        self.order_by = order_by

    def prepare_lookup(self, offset):
        def _invert_op(op):
            op_list = list(op)
            op_list[0] = "l" if op_list[0] == "g" else "g"
            return "".join(op_list)

        offset_object = self._cached_slice.get(pk=abs(offset))

        lookup_filter = {}

        for lookup in self.order_by:
            op = "lt" if offset < 0 else "gt"
            if lookup[0] == "-":
                op = _invert_op(op)
            cleaned_lookup = lookup.lstrip("-")

            lookup_filter["%s__%s" % (cleaned_lookup, op)] = \
                getattr(offset_object, cleaned_lookup)

        return lookup_filter

    def get_offset(self, limit):
        """
        Determines the proper starting offset of results to return.

        It attempts to use the user-provided ``offset`` from the GET parameters,
        if specified. Otherwise, it falls back to the object-level ``offset``.

        Default is 0.
        """
        offset = self.offset

        if 'offset' in self.request_data:
            offset = self.request_data['offset']

        try:
            offset = int(offset)
        except ValueError:
            raise BadRequest("Invalid offset '%s' provided. "
                             "Please provide an integer." % offset)

        if offset == 0:
            objects, is_qs = self.get_slice(limit, offset)

            if is_qs:
                if objects:
                    offset = objects[0].pk
                else:
                    offset = None

        return offset

    def get_slice(self, limit, offset):
        """
        Slices the result set to the specified ``limit`` & ``offset``.
        """
        if self._cached_slice:
            return self._cached_slice, self._cached_slice_is_qs

        # FIXME: index pagination on the non-standard querysets and lists
        if not self.order_by:
            self._cached_slice = super(InfiniteScrollPaginator, self).get_slice(
                limit, offset)
            self._cached_slice_is_qs = False
            return self._cached_slice, self._cached_slice_is_qs

        self._cached_slice = self.objects
        self._cached_slice_is_qs = True

        try:
            lookup_filter = self.prepare_lookup(offset)
            self._cached_slice = self._cached_slice.filter(**lookup_filter)
        except (AttributeError, TypeError, ObjectDoesNotExist):
            # If it's not a QuerySet (or it's ilk), fallback forward.
            pass

        if limit != 0:
            if offset < 0:
                self._cached_slice = reversed(
                    self._cached_slice.reverse()[:limit])
            else:
                self._cached_slice = self._cached_slice[:limit]
        self._cached_slice = list(self._cached_slice)
        return self._cached_slice, self._cached_slice_is_qs

    def get_previous(self, limit, offset):
        """
        If a previous page is available, will generate a URL to request that
        page. If not available, this returns ``None``.
        """
        return None

    def get_next(self, limit, offset, count):
        """
        If a next page is available, will generate a URL to request that
        page. If not available, this returns ``None``.
        """
        objects, is_qs = self.get_slice(limit, offset)

        if len(objects) < limit:
            return None

        if is_qs:
            if offset < 0:
                return -objects[0].pk
            return objects[-1].pk
        return offset + limit

    def page(self):
        """
        Generates all pertinent data about the requested page.

        Handles getting the correct ``limit`` & ``offset``, then slices off
        the correct set of results and returns all pertinent metadata.
        """
        limit = self.get_limit()
        offset = self.get_offset(limit)
        objects, _ = self.get_slice(limit, offset)

        meta = {
            'offset': offset,
            'limit': limit,
        }

        if limit:
            meta['next'] = self.get_next(limit, offset, self.get_count())

        return {
            self.collection_name: objects,
            'meta': meta,
        }
