// AUTEUR : TEUGUIA TADJUIDJE Rodolf Séderis — Rihen
// =============================================================================
// police.h — la police système que les épreuves NKFont ouvrent, selon le système qui les lance : Arial sous
// Windows et macOS, DejaVu Sans sous Linux (paquet fonts-dejavu-core, installé par le flux).
// =============================================================================
#pragma once

#if defined(_WIN32)
#define NK_EPREUVE_POLICE "C:/Windows/Fonts/arial.ttf"
#elif defined(__APPLE__)
#define NK_EPREUVE_POLICE "/System/Library/Fonts/Supplemental/Arial.ttf"
#else
#define NK_EPREUVE_POLICE "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
#endif
