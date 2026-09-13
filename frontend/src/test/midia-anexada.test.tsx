/**
 * "Mídia anexada": o relato com foto avisa que ela foi junto e a abre numa aba
 * nova, sem embutir a imagem espremida na lista.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { MidiaAnexada } from "@/components/relatos/MidiaAnexada";
import { mockServer } from "./server";

afterEach(() => vi.unstubAllGlobals());

it("abre a foto numa aba nova a partir de um blob, sem imagem embutida", async () => {
  mockServer({ "GET /relatos/r-1/foto": () => ({ status: 200, body: "png" }) });
  const aba = { location: { href: "" }, close: vi.fn() };
  vi.stubGlobal("open", vi.fn(() => aba));
  URL.createObjectURL = vi.fn(() => "blob:foto");
  URL.revokeObjectURL = vi.fn();

  const { container } = render(<MidiaAnexada relatoId="r-1" />);
  expect(container.querySelector("img")).toBeNull();

  await userEvent.click(screen.getByRole("button", { name: /Mídia anexada/ }));
  expect(window.open).toHaveBeenCalledWith("", "_blank");
  await waitFor(() => expect(aba.location.href).toBe("blob:foto"));
});
