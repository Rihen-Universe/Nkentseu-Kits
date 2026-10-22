// AUTEUR : TEUGUIA TADJUIDJE Rodolf Séderis — Rihen
// =============================================================================
// retours.cpp — le programme d'un apprenant, construit CONTRE UN KIT : les corrections du 21/10/2026
// sont-elles dans le kit ? (sans la bibliotheque standard)
//   - NkFormat : cinq « {} », cinq valeurs a leur place ;
//   - NkAddress(172, 16, 0, 1, 8080).ToString() == "172.16.0.1:8080" (compile dans NKNetwork) ;
//   - WriteF32Q / ReadF32Q : 500 et 360 reviennent exacts (compile dans NKNetwork) ;
//   - NkFuture.h et NkPromise<void> s'emploient ;
//   - NkSharedPtr<Derivee> se passe ou l'on attend NkSharedPtr<Base>.
// Imprime « retours : 5/5 » et rend 0 si tout est juste ; sinon dit lequel et rend 1.
// =============================================================================
#include "NKContainers/String/NkFormat.h"
#include "NKContainers/String/NkPrint.h"
#include "NKMemory/NkSharedPtr.h"
#include "NKNetwork/Protocol/NkBitStream.h"
#include "NKNetwork/Transport/NkSocket.h"
#include "NKThreading/NkFuture.h"

using namespace nkentseu;

namespace {
	struct Base {
			virtual ~Base() = default;
			int v = 7;
	};
	struct Derivee : Base {};
	int Lire(const memory::NkSharedPtr<Base> &b) {
		return b ? b->v : -1;
	}
	bool Egal(const NkString &s, const char *a) {
		return s == NkString(a);
	}
} // namespace

int main() {
	int justes = 0;
	const NkString f = NkFormat("{}.{}.{}.{}:{}", 172u, 16u, 0u, 1u, 8080u);
	if (Egal(f, "172.16.0.1:8080"))
		++justes;
	else
		NkPrintln("NkFormat : {}", f);

	const NkString a = net::NkAddress(172, 16, 0, 1, 8080).ToString();
	if (Egal(a, "172.16.0.1:8080"))
		++justes;
	else
		NkPrintln("NkAddress::ToString : {}", a);

	uint8 tampon[16] = {};
	net::NkBitWriter w(tampon, sizeof(tampon));
	w.WriteF32Q(500.f, -500.f, 500.f, 0.01f);
	w.WriteF32Q(360.f, 0.f, 360.f, 0.5f);
	net::NkBitReader r(tampon, sizeof(tampon));
	const float32 m1 = r.ReadF32Q(-500.f, 500.f, 0.01f);
	const float32 m2 = r.ReadF32Q(0.f, 360.f, 0.5f);
	if (m1 == 500.f && m2 == 360.f)
		++justes;
	else
		NkPrintln("WriteF32Q : {} et {}", m1, m2);

	threading::NkPromise<void> p;
	threading::NkFuture<void> fu = p.GetFuture();
	const bool avant = fu.IsReady();
	p.SetValue();
	if (!avant && fu.IsReady())
		++justes;
	else
		NkPrintln("NkFuture : pret avant {} apres {}", avant, fu.IsReady());

	if (Lire(memory::NkMakeShared<Derivee>()) == 7)
		++justes;
	else
		NkPrintln("NkSharedPtr : conversion");

	NkPrintln("retours : {}/5", justes);
	return justes == 5 ? 0 : 1;
}
