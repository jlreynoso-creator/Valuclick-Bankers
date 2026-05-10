import { drizzle } from "drizzle-orm/netlify-db";
import * as schema from "./schema.js";

const db = drizzle({ schema });
export default db;
export { schema };
