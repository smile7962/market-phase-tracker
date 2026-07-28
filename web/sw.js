/* 서비스 워커.
 * - HTML(앱 셸)·data.json·history.json: 네트워크 우선(오프라인 시 캐시 폴백)
 *   → UI/데이터 갱신이 즉시 반영되고, 오프라인에서도 마지막 버전이 뜬다.
 * - 아이콘·매니페스트 등 정적 자산: 캐시 우선.
 * 캐시 버전을 올리면 activate에서 옛 캐시를 지워 강제 갱신된다. */
const CACHE = "mpt-v3";
const SHELL = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

function networkFirst(req) {
  return fetch(req)
    .then((r) => {
      const copy = r.clone();
      caches.open(CACHE).then((c) => c.put(req, copy));
      return r;
    })
    .catch(() => caches.match(req).then((r) => r || caches.match("./index.html")));
}

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  const isHTML =
    e.request.mode === "navigate" ||
    url.pathname.endsWith("/") ||
    url.pathname.endsWith(".html");
  const isData =
    url.pathname.endsWith("data.json") || url.pathname.endsWith("history.json");

  if (isHTML || isData) {
    e.respondWith(networkFirst(e.request));
    return;
  }
  // 정적 자산은 캐시 우선
  e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)));
});
