/* 서비스 워커 — 앱 셸은 캐시 우선, data.json은 네트워크 우선(오프라인 폴백). */
const CACHE = "mpt-v1";
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

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // 데이터는 항상 최신 우선, 실패 시 캐시
  if (url.pathname.endsWith("data.json") || url.pathname.endsWith("history.json")) {
    e.respondWith(
      fetch(e.request)
        .then((r) => {
          const copy = r.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
          return r;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }
  // 앱 셸은 캐시 우선
  e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)));
});
