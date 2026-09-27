// Minimal service worker: lets phones install the toolkit as an app. It doesn't cache
// anything - the toolkit always talks live to your PC.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
