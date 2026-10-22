// AUTEUR : TEUGUIA TADJUIDJE Rodolf Séderis — Rihen
// =============================================================================
// pan.cpp — épreuve du kit NKAudio : un son placé DEVANT l'écouteur doit sortir des deux côtés à égalité
// (le panoramique 3D). Sortie NULL : aucun périphérique audio n'est ouvert, le mixage se lit en mémoire.
// Sans la bibliothèque standard.
// Code 0 si le panoramique est juste, 1 s'il est faux, 2 si le moteur ne démarre pas.
// =============================================================================
#include "NKAudio/NkAudio.h"
#include "NKContainers/String/NkPrint.h"

using namespace nkentseu;
using namespace nkentseu::audio;

int main() {
	AudioEngineConfig cfg;
	cfg.backend = AudioBackendType::NULL_OUTPUT;
	cfg.sampleRate = 48000;
	cfg.channels = 2;
	cfg.bufferSize = 256;
	if (!AudioEngine::Instance().Initialize(cfg)) {
		NkPrintln("moteur non initialise");
		return 2;
	}
	AudioSample son = AudioGenerator::GenerateTone(440.0f, 1.0f);
	VoiceParams vp;
	vp.source3d.positional = true;
	vp.source3d.position[2] = -2.0f; // devant (l'écouteur regarde vers -Z)
	AudioEngine::Instance().Play(son, vp);
	static float tampon[4800 * 2];
	AudioEngine::Instance().RenderToBuffer(tampon, 4800, 2);
	double g = 0.0, d = 0.0;
	for (int i = 0; i < 4800; ++i) {
		g += static_cast<double>(tampon[2 * i]) * tampon[2 * i];
		d += static_cast<double>(tampon[2 * i + 1]) * tampon[2 * i + 1];
	}
	NkPrintln("source devant : energie gauche {:.3f}, droite {:.3f}", g, d);
	AudioLoader::Free(son);
	AudioEngine::Instance().Shutdown();
	const bool juste = g > 1.0 && d > 1.0 && g > 0.95 * d && d > 0.95 * g;
	NkPrintln("{}", juste ? "PANORAMIQUE JUSTE" : "PANORAMIQUE FAUX");
	return juste ? 0 : 1;
}
