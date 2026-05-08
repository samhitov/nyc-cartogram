const PATH_PREFIXES = ["/nyc", "/boston", "/chicago", "/philadelphia", "/montreal"];
const DIAGNOSTIC_HEADER = "x-nyc-cartogram-worker";

function withoutPrefix(pathname) {
  for (const prefix of PATH_PREFIXES) {
    if (pathname === prefix || pathname === `${prefix}/`) return { prefix, path: "/" };
    if (pathname.startsWith(`${prefix}/`)) {
      return { prefix, path: pathname.slice(prefix.length) };
    }
  }
  return null;
}

function withDiagnosticHeader(response) {
  const headers = new Headers(response.headers);
  headers.set(DIAGNOSTIC_HEADER, "1");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function rewriteAssetRedirect(requestUrl, prefix, response) {
  const location = response.headers.get("location");
  if (!location) return response;

  const resolved = new URL(location, requestUrl);
  if (resolved.origin !== requestUrl.origin) return response;
  if (!resolved.pathname.startsWith("/")) return response;
  if (PATH_PREFIXES.some((prefix) => resolved.pathname.startsWith(prefix))) return response;

  const headers = new Headers(response.headers);
  headers.set("location", `${prefix}${resolved.pathname}${resolved.search}`);
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    const rewrite = withoutPrefix(url.pathname);

    if (rewrite === null) {
      return withDiagnosticHeader(new Response("Not found", { status: 404 }));
    }

    const rewrittenPath = rewrite.path;
    url.pathname = rewrittenPath === "/" || rewrittenPath.startsWith("/@") ? "/" : rewrittenPath;
    const assetRequest = new Request(url.toString(), request);
    const assetResponse = await env.ASSETS.fetch(assetRequest);
    return withDiagnosticHeader(rewriteAssetRedirect(url, rewrite.prefix, assetResponse));
  },
};
