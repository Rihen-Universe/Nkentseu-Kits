// AUTEUR : TEUGUIA TADJUIDJE Rodolf Séderis — Rihen
// =============================================================================
// fils.cpp — épreuve du kit NKThreading (et de ceux qui l'embarquent) : 1 000 tâches sur une réserve de
// 4 fils, chacune incrémente un total sous un verrou, comme dans l'énoncé d'ANI-2053. Le `new` passe par la
// mémoire du moteur (NKMemory remplace operator new). Sans la bibliothèque standard.
// Code 0 si le total vaut 1 000, 1 sinon.
// =============================================================================
#include "NKContainers/String/NkPrint.h"
#include "NKThreading/NkMutex.h"
#include "NKThreading/NkScopedLock.h"
#include "NKThreading/NkThreadPool.h"

// La ligne exacte d'un énoncé : `using namespace nkentseu::threading;` SEUL (avec aussi `using namespace
// nkentseu;`, NkScopedLock devient ambigu : nkentseu::NkScopedLock existe aussi).
using namespace nkentseu::threading;

int main() {
	NkMutex verrou;
	int total = 0;
	int *tas = new int(7);
	{
		NkThreadPool reserve(4);
		for (int i = 0; i < 1000; ++i) {
			reserve.Enqueue([&verrou, &total]() {
				NkScopedLock<NkMutex> l(verrou);
				++total;
			});
		}
		reserve.Join();
	}
	nkentseu::NkPrintln("total {} (attendu 1000), tas {}", total, *tas);
	delete tas;
	return total == 1000 ? 0 : 1;
}
