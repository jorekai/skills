// The app reads the packages as TypeScript source, so the four of them are transpiled here.
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@app/config", "@app/env", "@app/ui", "@app/ports"],
};

export default nextConfig;
