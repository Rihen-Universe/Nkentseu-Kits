// AUTEUR : TEUGUIA TADJUIDJE Rodolf Séderis — Rihen
// =============================================================================
// sdf.cpp — épreuve du kit NKFont, le cas de l'exercice « Le SDF, mesure » (sprint 5, 14/10) : un atlas avec
// `sdfMode = true`. Chaque glyphe de l'atlas SDF doit porter le SDF de SA propre image (celle d'un atlas
// ordinaire, même police, même taille). Avec le kit du 13/10, l'atlas SDF sortait corrompu. Sans la
// bibliothèque standard.
// Code 0 juste, 1 corrompu, 2 rien construit.
// =============================================================================
#include "NKContainers/String/NkPrint.h"
#include "NKFont/Core/NkFontParser.h"
#include "NKFont/NkFont.h"
#include "police.h"

using namespace nkentseu;

namespace {
	NkFontAtlas *Atlas(bool sdf, NkFont **police) {
		NkFontAtlas *atlas = new NkFontAtlas();
		atlas->sdfMode = sdf;
		atlas->sdfSpread = 4;
		NkFontConfig cfg;
		cfg.oversampleH = 1;
		cfg.oversampleV = 1;
		*police = atlas->AddFontFromFile(NK_EPREUVE_POLICE, 18.f, &cfg);
		if (!*police || !atlas->Build()) {
			delete atlas;
			return nullptr;
		}
		return atlas;
	}

	int Px(float uv, int taille) {
		return static_cast<int>(uv * static_cast<float>(taille) + 0.5f);
	}
} // namespace

int main() {
	NkFont *pN = nullptr, *pS = nullptr;
	NkFontAtlas *normal = Atlas(false, &pN);
	NkFontAtlas *sdf = Atlas(true, &pS);
	if (!normal || !sdf) {
		NkPrintln("sdf : atlas NON construit ({})", NK_EPREUVE_POLICE);
		delete normal;
		delete sdf;
		return 2;
	}
	nkft_uint8 *pxN = nullptr, *pxS = nullptr;
	nkft_int32 lN = 0, hN = 0, lS = 0, hS = 0;
	normal->GetTexDataAsAlpha8(&pxN, &lN, &hN);
	sdf->GetTexDataAsAlpha8(&pxS, &lS, &hS);
	static nkft_uint8 image[128 * 128], attendu[128 * 128];
	int glyphes = 0, justes = 0;
	for (const char *c = "ABgWm?"; *c; ++c) {
		const NkFontGlyph *gN = pN->FindGlyphNoFallback(static_cast<NkFontCodepoint>(*c));
		const NkFontGlyph *gS = pS->FindGlyphNoFallback(static_cast<NkFontCodepoint>(*c));
		if (!gN || !gS || !gN->visible || !gS->visible)
			continue;
		const int xN = Px(gN->u0, lN), yN = Px(gN->v0, hN), w = Px(gN->u1, lN) - xN, h = Px(gN->v1, hN) - yN;
		const int xS = Px(gS->u0, lS), yS = Px(gS->v0, hS);
		if (w <= 0 || h <= 0 || w > 128 || h > 128 || Px(gS->u1, lS) - xS != w || Px(gS->v1, hS) - yS != h)
			continue;
		++glyphes;
		for (int y = 0; y < h; ++y)
			for (int x = 0; x < w; ++x)
				image[y * w + x] = pxN[(yN + y) * lN + xN + x];
		nkfont::NkMakeSDFFromBitmap(image, w, h, attendu, 4);
		bool memes = true;
		for (int y = 0; y < h && memes; ++y)
			for (int x = 0; x < w && memes; ++x)
				memes = pxS[(yS + y) * lS + xS + x] == attendu[y * w + x];
		justes += memes ? 1 : 0;
	}
	NkPrintln("sdf : {} glyphe(s) sur {} portent le SDF de leur image", justes, glyphes);
	delete normal;
	delete sdf;
	return (glyphes >= 4 && justes == glyphes) ? 0 : 1;
}
