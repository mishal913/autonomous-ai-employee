import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  "http://localhost:8000";

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 180000,
  withCredentials: true,
});

api.interceptors.response.use(
  (response) => response,

  (error) => {
    const status = error?.response?.status;
    const url = String(error?.config?.url ?? "");

    if (
      status === 401 &&
      !url.includes("/auth/login")
    ) {
      window.dispatchEvent(
        new Event("auth:expired")
      );
    }

    return Promise.reject(error);
  }
);
