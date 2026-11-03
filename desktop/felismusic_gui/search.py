"""Honor the server-selected tab in filtered Library search responses."""
from copy import copy


def _library_tab_first(response):
    if not isinstance(response, dict):
        return response
    contents = response.get('contents')
    if not isinstance(contents, dict):
        return response
    renderer = contents.get('tabbedSearchResultsRenderer')
    if not isinstance(renderer, dict) or not isinstance(renderer.get('tabs'), list):
        return response
    tabs = renderer['tabs']
    selected = [index for index, tab in enumerate(tabs)
                if isinstance(tab, dict) and isinstance(tab.get('tabRenderer'), dict)
                and tab['tabRenderer'].get('selected') is True]
    if len(selected) > 1:
        raise ValueError('Ambiguous selected search tab')
    if not selected or selected[0] == 0:
        return response
    index = selected[0]
    # ytmusicapi reads tab 0 whenever a filter is present. Preserve its public
    # parser (including continuations), but feed it the tab selected by YTM.
    # Never mutate the response or the shared authenticated client.
    return dict(response, contents=dict(contents, tabbedSearchResultsRenderer=dict(
        renderer, tabs=[tabs[index], *tabs[:index], *tabs[index + 1:]])))


def search_music(api, query, **kwargs):
    if kwargs.get('scope') != 'library' or kwargs.get('filter') not in ('songs', 'albums', 'artists'):
        return api.search(query, **kwargs)
    client = copy(api)
    send = api._send_request

    def capture(endpoint, *args, **request_kwargs):
        response = send(endpoint, *args, **request_kwargs)
        return _library_tab_first(response) if endpoint == 'search' else response

    client._send_request = capture
    return client.search(query, **kwargs)
