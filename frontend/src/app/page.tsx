import ChatWidget from "@/components/ChatWidget";
import { Building2, MapPin, DollarSign, Bed } from "lucide-react";

export default function Home() {
  return (
    <main className="min-h-screen">
      {/* Hero Section */}
      <section className="relative bg-gradient-to-br from-primary-900 via-primary-800 to-primary-700 text-white">
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 lg:py-32">
          <div className="text-center">
            <div className="flex items-center justify-center gap-3 mb-6">
              <Building2 className="w-12 h-12" />
              <h1 className="text-3xl lg:text-4xl font-bold">
                Silver Land Properties
              </h1>
            </div>
            <p className="text-xl lg:text-2xl text-primary-100 max-w-3xl mx-auto mb-8">
              Discover your perfect property with our AI-powered assistant.
              Luxury homes, apartments, and villas worldwide.
            </p>
            <div className="flex flex-wrap justify-center gap-4 text-sm">
              <div className="flex items-center gap-2 bg-white/10 px-4 py-2 rounded-full">
                <MapPin className="w-4 h-4" />
                <span>Global Properties</span>
              </div>
              <div className="flex items-center gap-2 bg-white/10 px-4 py-2 rounded-full">
                <DollarSign className="w-4 h-4" />
                <span>Premium Listings</span>
              </div>
              <div className="flex items-center gap-2 bg-white/10 px-4 py-2 rounded-full">
                <Bed className="w-4 h-4" />
                <span>1-5 Bedrooms</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-16 lg:py-24 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-2xl lg:text-3xl font-bold text-silver-900 mb-4">
              How Can We Help You?
            </h2>
            <p className="text-silver-600 max-w-2xl mx-auto">
              Our AI assistant is ready to help you find the perfect property.
              Just click the chat button to get started.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <div className="text-center p-6 rounded-2xl bg-silver-50 hover:bg-silver-100 transition-colors">
              <div className="w-14 h-14 bg-primary-100 text-primary-600 rounded-xl flex items-center justify-center mx-auto mb-4">
                <MapPin className="w-7 h-7" />
              </div>
              <h3 className="font-semibold text-silver-900 mb-2">
                Find Your Location
              </h3>
              <p className="text-sm text-silver-600">
                Tell us your preferred city or country, and we&apos;ll show you
                available properties in that area.
              </p>
            </div>

            <div className="text-center p-6 rounded-2xl bg-silver-50 hover:bg-silver-100 transition-colors">
              <div className="w-14 h-14 bg-primary-100 text-primary-600 rounded-xl flex items-center justify-center mx-auto mb-4">
                <DollarSign className="w-7 h-7" />
              </div>
              <h3 className="font-semibold text-silver-900 mb-2">
                Set Your Budget
              </h3>
              <p className="text-sm text-silver-600">
                Share your budget range and we&apos;ll filter properties that
                match your financial requirements.
              </p>
            </div>

            <div className="text-center p-6 rounded-2xl bg-silver-50 hover:bg-silver-100 transition-colors">
              <div className="w-14 h-14 bg-primary-100 text-primary-600 rounded-xl flex items-center justify-center mx-auto mb-4">
                <Building2 className="w-7 h-7" />
              </div>
              <h3 className="font-semibold text-silver-900 mb-2">
                Book a Viewing
              </h3>
              <p className="text-sm text-silver-600">
                Once you find a property you like, schedule a viewing directly
                through our assistant.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 bg-silver-100">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-2xl lg:text-3xl font-bold text-silver-900 mb-4">
            Ready to Find Your Dream Property?
          </h2>
          <p className="text-silver-600 mb-8">
            Click the chat button in the bottom right corner to start your
            property search journey with our AI assistant.
          </p>
          <div className="inline-flex items-center gap-2 text-primary-600 font-medium">
            <span>Click the chat icon to begin</span>
            <span className="animate-bounce">↓</span>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-silver-900 text-silver-400 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-sm">
          <p>&copy; 2024 Silver Land Properties. All rights reserved.</p>
        </div>
      </footer>

      {/* Chat Widget */}
      <ChatWidget />
    </main>
  );
}
