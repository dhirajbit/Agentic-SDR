import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

// Public surface: marketing home, auth pages, and the cron endpoint (which
// authenticates via a cron secret, not Clerk). Everything else requires sign-in.
const isPublic = createRouteMatcher([
  "/",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/api/cron(.*)",
  "/api/whatsapp/webhook", // OpenWA posts here; authed by its own token
]);

export default clerkMiddleware(async (auth, req) => {
  if (!isPublic(req)) {
    await auth.protect();
  }
});

export const config = {
  matcher: [
    // Skip Next internals and static files, run on everything else + API routes.
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
