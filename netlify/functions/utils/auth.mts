import * as jose from "jose";
import bcrypt from "bcryptjs";

const SECRET_KEY = Netlify.env.get("SECRET_KEY") || "default-secret-change-in-production";
const ALGORITHM = "HS256";
const ACCESS_TOKEN_EXPIRE_DAYS = 30;

const secret = new TextEncoder().encode(SECRET_KEY);

export async function hashPassword(password: string): Promise<string> {
  return bcrypt.hashSync(password, 10);
}

export async function verifyPassword(
  plain: string,
  hashed: string,
): Promise<boolean> {
  return bcrypt.compareSync(plain, hashed);
}

export async function createAccessToken(
  userId: number,
  email: string,
): Promise<string> {
  const jwt = await new jose.SignJWT({ sub: email, user_id: userId })
    .setProtectedHeader({ alg: ALGORITHM })
    .setExpirationTime(`${ACCESS_TOKEN_EXPIRE_DAYS}d`)
    .sign(secret);
  return jwt;
}

export async function verifyToken(
  token: string,
): Promise<{ email: string; userId: number } | null> {
  try {
    const { payload } = await jose.jwtVerify(token, secret);
    const email = payload.sub as string;
    const userId = payload.user_id as number;
    if (!email || !userId) return null;
    return { email, userId };
  } catch {
    return null;
  }
}

export async function getUserFromRequest(
  request: Request,
): Promise<{ email: string; userId: number } | null> {
  const authHeader = request.headers.get("Authorization");
  if (!authHeader?.startsWith("Bearer ")) return null;
  const token = authHeader.slice(7);
  return verifyToken(token);
}

export function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function errorResponse(detail: string, status = 400): Response {
  return jsonResponse({ detail }, status);
}
