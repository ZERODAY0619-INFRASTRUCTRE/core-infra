// Reject proxy challenge pages before they enter Grafana's application state.
// Explicit text/binary and datasource/plugin proxy responses retain their contracts.
function validateGrafanaApiResponse(options, response, data) {
  const request = new URL(options.url, window.location.href);
  if (request.origin !== window.location.origin ||
      !/\/(?:api|apis)\//.test(request.pathname) ||
      /\/api\/(?:datasources\/proxy|plugins\/[^/]+\/resources)\//.test(request.pathname) ||
      (options.responseType && options.responseType !== 'json') || !response.ok) {
    return;
  }
  const html = typeof data === 'string' &&
    (/^\s*(?:<!doctype\s+html|<html\b)/i.test(data) ||
     /(?:text\/html|application\/xhtml\+xml)/i.test(response.headers.get('content-type') || ''));
  const arrayEndpoint = /\/api\/user\/(?:orgs|teams)\/?$/.test(request.pathname) ||
    /\/api\/alertmanager\/[^/]+\/api\/v2\/alerts\/?$/.test(request.pathname);
  if (html || (arrayEndpoint && !Array.isArray(data))) {
    throw {
      status: 502,
      statusText: 'Invalid API response',
      data: {message: 'The API returned an unexpected response. Reload the page to complete any proxy verification, then retry.'},
      config: options,
    };
  }
}
