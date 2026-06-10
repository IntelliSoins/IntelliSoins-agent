import Foundation
import WebKit
import OSLog

private let browserLogger = Logger(subsystem: "ai.openclaw", category: "browser.manager")

@MainActor
public final class BrowserManager: NSObject, @preconcurrency WKNavigationDelegate {
    public static let shared = BrowserManager()
    
    private var webView: WKWebView?
    private var navigationContinuation: CheckedContinuation<Void, Error>?
    
    private override init() {
        super.init()
        let config = WKWebViewConfiguration()
        config.preferences.setValue(true, forKey: "developerExtrasEnabled")
        
        let web = WKWebView(frame: .zero, configuration: config)
        web.navigationDelegate = self
        web.customUserAgent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"
        self.webView = web
        browserLogger.debug("BrowserManager initialized headless WKWebView")
    }
    
    public func navigate(url: URL) async throws {
        guard let webView = self.webView else {
            throw NSError(domain: "BrowserManager", code: 1, userInfo: [NSLocalizedDescriptionKey: "WebView not initialized"])
        }
        
        browserLogger.debug("Navigating to URL: \(url.absoluteString, privacy: .public)")
        
        if let pending = navigationContinuation {
            self.navigationContinuation = nil
            pending.resume(throwing: CancellationError())
        }
        
        return try await withCheckedThrowingContinuation { continuation in
            self.navigationContinuation = continuation
            let request = URLRequest(url: url)
            webView.load(request)
        }
    }
    
    public func evaluate(javaScript: String) async throws -> String {
        guard let webView = self.webView else {
            throw NSError(domain: "BrowserManager", code: 1, userInfo: [NSLocalizedDescriptionKey: "WebView not initialized"])
        }
        
        browserLogger.debug("Evaluating JavaScript...")
        let result = try await webView.evaluateJavaScript(javaScript)
        
        if let str = result as? String {
            return str
        } else if let num = result as? NSNumber {
            return num.stringValue
        } else if let dict = result as? [String: Any] {
            if let data = try? JSONSerialization.data(withJSONObject: dict, options: []),
               let jsonString = String(data: data, encoding: .utf8) {
                return jsonString
            }
        } else if let arr = result as? [Any] {
            if let data = try? JSONSerialization.data(withJSONObject: arr, options: []),
               let jsonString = String(data: data, encoding: .utf8) {
                return jsonString
            }
        } else if let val = result {
            return String(describing: val)
        }
        return ""
    }
    
    // MARK: - WKNavigationDelegate
    
    public func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        browserLogger.debug("Navigation finished successfully")
        if let continuation = navigationContinuation {
            navigationContinuation = nil
            continuation.resume()
        }
    }
    
    public func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        browserLogger.error("Navigation failed: \(error.localizedDescription, privacy: .public)")
        if let continuation = navigationContinuation {
            navigationContinuation = nil
            continuation.resume(throwing: error)
        }
    }
    
    public func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        browserLogger.error("Provisional navigation failed: \(error.localizedDescription, privacy: .public)")
        if let continuation = navigationContinuation {
            navigationContinuation = nil
            continuation.resume(throwing: error)
        }
    }
}
