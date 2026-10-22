// AUTEUR : TEUGUIA TADJUIDJE Rodolf Séderis — Rihen
// =============================================================================
// police.cpp — épreuve du kit NKFont (et de NKCanvas, NKRenderer qui l'embarquent) : un atlas construit sans
// configuration doit porter de l'encre (le kit du 10/10 le rendait entièrement transparent), et la lettre A
// doit avancer. Sans la bibliothèque standard.
// Code 0 si l'atlas porte de l'encre, 1 sinon, 2 si rien n'est construit.
// =============================================================================
#include "NKContainers/String/NkPrint.h"
#include "NKFont/NkFont.h"
#include "police.h"

using namespace nkentseu;

int main() {
	NkFontAtlas *atlas = new NkFontAtlas();
	NkFont *police = atlas->AddFontFromFile(NK_EPREUVE_POLICE, 18.f);
	if (!police || !atlas->Build()) {
		NkPrintln("encre : atlas NON construit ({})", NK_EPREUVE_POLICE);
		delete atlas;
		return 2;
	}
	nkft_uint8 *px = nullptr;
	nkft_int32 l = 0, h = 0;
	atlas->GetTexDataAsAlpha8(&px, &l, &h);
	long long nonNuls = 0;
	for (long long i = 0; px && i < static_cast<long long>(l) * h; ++i)
		if (px[i] != 0)
			++nonNuls;
	const NkFontGlyph *a = police->FindGlyph('A');
	const double avance = a ? static_cast<double>(a->advanceX) : -1.0;
	NkPrintln("encre : {} octets non nuls sur {}x{}, avance de A {:.2f}", nonNuls, l, h, avance);
	delete atlas;
	return (nonNuls > 0 && avance > 0.0) ? 0 : 1;
}
