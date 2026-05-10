import type { Context } from "@netlify/functions";
import { eq } from "drizzle-orm";
import db from "../../db/index.js";
import { users } from "../../db/schema.js";
import {
  getUserFromRequest,
  jsonResponse,
  errorResponse,
} from "./utils/auth.mjs";

export default async function handler(request: Request, _context: Context) {
  if (request.method !== "GET") {
    return errorResponse("Method not allowed", 405);
  }

  const tokenData = await getUserFromRequest(request);
  if (!tokenData) {
    return errorResponse("No autorizado", 401);
  }

  const [user] = await db
    .select()
    .from(users)
    .where(eq(users.id, tokenData.userId))
    .limit(1);

  if (!user) {
    return errorResponse("Usuario no encontrado", 404);
  }

  const isFree = user.subscriptionPlan === "free";
  const isSubscriptionActive =
    !isFree &&
    user.subscriptionExpires !== null &&
    new Date() < new Date(user.subscriptionExpires);
  const remainingFree = isFree ? Math.max(0, 2 - user.searchCount) : 999;
  const canSearch = isFree ? user.searchCount < 2 : isSubscriptionActive;

  return jsonResponse({
    id: user.id,
    email: user.email,
    full_name: user.fullName,
    subscription_plan: user.subscriptionPlan,
    search_count: user.searchCount,
    remaining_free_searches: remainingFree,
    can_search: canSearch,
  });
}

export const config = {
  path: "/api/user/me",
  method: "GET",
};
