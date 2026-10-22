// AUTEUR : TEUGUIA TADJUIDJE Rodolf Séderis — Rihen
// =============================================================================
// reseau.cpp — épreuve du kit NKNetwork : un serveur et un client dans le même programme, sur 127.0.0.1
// SEULEMENT. Le client se connecte, envoie « bonjour » sur le canal fiable ordonné, le serveur répond
// « bienvenue ». Dix secondes au plus. Sans la bibliothèque standard (NkAtomic, NkChrono).
// Code 0 si « bienvenue » arrive, 1 sinon, 2 ou 3 si le serveur ou le client ne démarre pas.
// =============================================================================
#include "NKContainers/String/NkPrint.h"
#include "NKCore/NkAtomic.h"
#include "NKNetwork/Protocol/NkConnection.h"
#include "NKNetwork/Transport/NkSocket.h"
#include "NKTime/NkChrono.h"

using namespace nkentseu;
using namespace nkentseu::net;

namespace {
	template <typename Tampon> bool Pareil(const Tampon &donnees, const char *texte, int n) {
		for (int i = 0; i < n; ++i)
			if (static_cast<char>(donnees[i]) != texte[i])
				return false;
		return true;
	}

	const char *OuiNon(bool b) {
		return b ? "oui" : "non";
	}
} // namespace

int main() {
	const uint16 port = 47833;
	NkConnectionManager serveur, client;
	NkAtomicBool serveurVoitClient(false), clientConnecte(false);
	NkPeerId pairDuServeur, pairDuClient; // le client vu par le serveur ; le serveur vu par le client
	serveur.onPeerConnected = [&](NkPeerId p) {
		pairDuServeur = p;
		serveurVoitClient = true;
	};
	client.onPeerConnected = [&](NkPeerId p) {
		pairDuClient = p;
		clientConnecte = true;
	};

	if (serveur.StartServer(port, 4) != NkNetResult::NK_NET_OK) {
		NkPrintln("le serveur ne demarre pas sur le port {}", static_cast<unsigned>(port));
		return 2;
	}
	if (client.Connect(NkAddress::Loopback(port)) != NkNetResult::NK_NET_OK) {
		NkPrintln("le client ne se connecte pas");
		return 3;
	}
	bool bonjourRecu = false, bienvenueRecu = false, bonjourEnvoye = false;
	const NkElapsedTime debut = NkChrono::Now();
	while ((NkChrono::Now() - debut).ToMilliseconds() < 10000.0 && !bienvenueRecu) {
		if (clientConnecte && !bonjourEnvoye) {
			const char *m = "bonjour";
			bonjourEnvoye = client.SendTo(pairDuClient, reinterpret_cast<const uint8 *>(m), 8) == NkNetResult::NK_NET_OK;
		}
		NkVector<NkReceiveMsg> recus;
		serveur.DrainAll(recus);
		for (const NkReceiveMsg &r : recus) {
			if (r.size == 8 && Pareil(r.data, "bonjour", 8)) {
				bonjourRecu = true;
				const char *m = "bienvenue";
				(void)serveur.SendTo(r.from, reinterpret_cast<const uint8 *>(m), 10);
			}
		}
		NkVector<NkReceiveMsg> recusClient;
		client.DrainAll(recusClient);
		for (const NkReceiveMsg &r : recusClient) {
			if (r.size == 10 && Pareil(r.data, "bienvenue", 10))
				bienvenueRecu = true;
		}
		NkChrono::SleepMilliseconds(10);
	}
	const double ms = (NkChrono::Now() - debut).ToMilliseconds();
	NkPrintln("serveur voit le client : {} ; client connecte : {} ; bonjour recu : {} ; bienvenue recue : {} ({:.0f} ms)",
			  OuiNon(serveurVoitClient), OuiNon(clientConnecte), OuiNon(bonjourRecu), OuiNon(bienvenueRecu), ms);
	client.Shutdown();
	serveur.Shutdown();
	return bienvenueRecu ? 0 : 1;
}
