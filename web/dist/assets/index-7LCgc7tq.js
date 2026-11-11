(function(){let e=document.createElement(`link`).relList;if(e&&e.supports&&e.supports(`modulepreload`))return;for(let e of document.querySelectorAll(`link[rel="modulepreload"]`))n(e);new MutationObserver(e=>{for(let t of e)if(t.type===`childList`)for(let e of t.addedNodes)e.tagName===`LINK`&&e.rel===`modulepreload`&&n(e)}).observe(document,{childList:!0,subtree:!0});function t(e){let t={};return e.integrity&&(t.integrity=e.integrity),e.referrerPolicy&&(t.referrerPolicy=e.referrerPolicy),t.credentials=e.crossOrigin===`use-credentials`?`include`:e.crossOrigin===`anonymous`?`omit`:`same-origin`,t}function n(e){if(e.ep)return;e.ep=!0;let n=t(e);fetch(e.href,n)}})();var e=globalThis,t=e.ShadowRoot&&(e.ShadyCSS===void 0||e.ShadyCSS.nativeShadow)&&`adoptedStyleSheets`in Document.prototype&&`replace`in CSSStyleSheet.prototype,n=Symbol(),r=new WeakMap,i=class{constructor(e,t,r){if(this._$cssResult$=!0,r!==n)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,n=this.t;if(t&&e===void 0){let t=n!==void 0&&n.length===1;t&&(e=r.get(n)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),t&&r.set(n,e))}return e}toString(){return this.cssText}},a=e=>new i(typeof e==`string`?e:e+``,void 0,n),o=(e,...t)=>new i(e.length===1?e[0]:t.reduce((t,n,r)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if(typeof e==`number`)return e;throw Error(`Value passed to 'css' function must be a 'css' function result: `+e+`. Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.`)})(n)+e[r+1],e[0]),e,n),s=(n,r)=>{if(t)n.adoptedStyleSheets=r.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let t of r){let r=document.createElement(`style`),i=e.litNonce;i!==void 0&&r.setAttribute(`nonce`,i),r.textContent=t.cssText,n.appendChild(r)}},c=t?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t=``;for(let n of e.cssRules)t+=n.cssText;return a(t)})(e):e,{is:l,defineProperty:u,getOwnPropertyDescriptor:d,getOwnPropertyNames:ee,getOwnPropertySymbols:te,getPrototypeOf:ne}=Object,f=globalThis,re=f.trustedTypes,ie=re?re.emptyScript:``,ae=f.reactiveElementPolyfillSupport,p=(e,t)=>e,m={toAttribute(e,t){switch(t){case Boolean:e=e?ie:null;break;case Object:case Array:e=e==null?e:JSON.stringify(e)}return e},fromAttribute(e,t){let n=e;switch(t){case Boolean:n=e!==null;break;case Number:n=e===null?null:Number(e);break;case Object:case Array:try{n=JSON.parse(e)}catch{n=null}}return n}},h=(e,t)=>!l(e,t),oe={attribute:!0,type:String,converter:m,reflect:!1,useDefault:!1,hasChanged:h};Symbol.metadata??=Symbol(`metadata`),f.litPropertyMetadata??=new WeakMap;var g=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=oe){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let n=Symbol(),r=this.getPropertyDescriptor(e,n,t);r!==void 0&&u(this.prototype,e,r)}}static getPropertyDescriptor(e,t,n){let{get:r,set:i}=d(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:r,set(t){let a=r?.call(this);i?.call(this,t),this.requestUpdate(e,a,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??oe}static _$Ei(){if(this.hasOwnProperty(p(`elementProperties`)))return;let e=ne(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(p(`finalized`)))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(p(`properties`))){let e=this.properties,t=[...ee(e),...te(e)];for(let n of t)this.createProperty(n,e[n])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[e,n]of t)this.elementProperties.set(e,n)}this._$Eh=new Map;for(let[e,t]of this.elementProperties){let n=this._$Eu(e,t);n!==void 0&&this._$Eh.set(n,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let n=new Set(e.flat(1/0).reverse());for(let e of n)t.unshift(c(e))}else e!==void 0&&t.push(c(e));return t}static _$Eu(e,t){let n=t.attribute;return!1===n?void 0:typeof n==`string`?n:typeof e==`string`?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let n of t.keys())this.hasOwnProperty(n)&&(e.set(n,this[n]),delete this[n]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return s(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,n){this._$AK(e,n)}_$ET(e,t){let n=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,n);if(r!==void 0&&!0===n.reflect){let i=(n.converter?.toAttribute===void 0?m:n.converter).toAttribute(t,n.type);this._$Em=e,i==null?this.removeAttribute(r):this.setAttribute(r,i),this._$Em=null}}_$AK(e,t){let n=this.constructor,r=n._$Eh.get(e);if(r!==void 0&&this._$Em!==r){let e=n.getPropertyOptions(r),i=typeof e.converter==`function`?{fromAttribute:e.converter}:e.converter?.fromAttribute===void 0?m:e.converter;this._$Em=r;let a=i.fromAttribute(t,e.type);this[r]=a??this._$Ej?.get(r)??a,this._$Em=null}}requestUpdate(e,t,n,r=!1,i){if(e!==void 0){let a=this.constructor;if(!1===r&&(i=this[e]),n??=a.getPropertyOptions(e),!((n.hasChanged??h)(i,t)||n.useDefault&&n.reflect&&i===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,n))))return;this.C(e,t,n)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:n,reflect:r,wrapped:i},a){n&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,a??t??this[e]),!0!==i||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||n||(t=void 0),this._$AL.set(e,t)),!0===r&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}let e=this.constructor.elementProperties;if(e.size>0)for(let[t,n]of e){let{wrapped:e}=n,r=this[t];!0!==e||this._$AL.has(t)||r===void 0||this.C(t,void 0,n,r)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};g.elementStyles=[],g.shadowRootOptions={mode:`open`},g[p(`elementProperties`)]=new Map,g[p(`finalized`)]=new Map,ae?.({ReactiveElement:g}),(f.reactiveElementVersions??=[]).push(`2.1.2`);var _=globalThis,se=e=>e,v=_.trustedTypes,ce=v?v.createPolicy(`lit-html`,{createHTML:e=>e}):void 0,le=`$lit$`,y=`lit$${Math.random().toFixed(9).slice(2)}$`,ue=`?`+y,de=`<${ue}>`,b=document,x=()=>b.createComment(``),S=e=>e===null||typeof e!=`object`&&typeof e!=`function`,C=Array.isArray,fe=e=>C(e)||typeof e?.[Symbol.iterator]==`function`,w=`[ 	
\f\r]`,T=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,pe=/-->/g,me=/>/g,E=RegExp(`>|${w}(?:([^\\s"'>=/]+)(${w}*=${w}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,`g`),he=/'/g,ge=/"/g,_e=/^(?:script|style|textarea|title)$/i,D=(e=>(t,...n)=>({_$litType$:e,strings:t,values:n}))(1),O=Symbol.for(`lit-noChange`),k=Symbol.for(`lit-nothing`),ve=new WeakMap,A=b.createTreeWalker(b,129);function ye(e,t){if(!C(e)||!e.hasOwnProperty(`raw`))throw Error(`invalid template strings array`);return ce===void 0?t:ce.createHTML(t)}var be=(e,t)=>{let n=e.length-1,r=[],i,a=t===2?`<svg>`:t===3?`<math>`:``,o=T;for(let t=0;t<n;t++){let n=e[t],s,c,l=-1,u=0;for(;u<n.length&&(o.lastIndex=u,c=o.exec(n),c!==null);)u=o.lastIndex,o===T?c[1]===`!--`?o=pe:c[1]===void 0?c[2]===void 0?c[3]!==void 0&&(o=E):(_e.test(c[2])&&(i=RegExp(`</`+c[2],`g`)),o=E):o=me:o===E?c[0]===`>`?(o=i??T,l=-1):c[1]===void 0?l=-2:(l=o.lastIndex-c[2].length,s=c[1],o=c[3]===void 0?E:c[3]===`"`?ge:he):o===ge||o===he?o=E:o===pe||o===me?o=T:(o=E,i=void 0);let d=o===E&&e[t+1].startsWith(`/>`)?` `:``;a+=o===T?n+de:l>=0?(r.push(s),n.slice(0,l)+le+n.slice(l)+y+d):n+y+(l===-2?t:d)}return[ye(e,a+(e[n]||`<?>`)+(t===2?`</svg>`:t===3?`</math>`:``)),r]},j=class e{constructor({strings:t,_$litType$:n},r){let i;this.parts=[];let a=0,o=0,s=t.length-1,c=this.parts,[l,u]=be(t,n);if(this.el=e.createElement(l,r),A.currentNode=this.el.content,n===2||n===3){let e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;(i=A.nextNode())!==null&&c.length<s;){if(i.nodeType===1){if(i.hasAttributes())for(let e of i.getAttributeNames())if(e.endsWith(le)){let t=u[o++],n=i.getAttribute(e).split(y),r=/([.?@])?(.*)/.exec(t);c.push({type:1,index:a,name:r[2],strings:n,ctor:r[1]===`.`?Se:r[1]===`?`?Ce:r[1]===`@`?we:P}),i.removeAttribute(e)}else e.startsWith(y)&&(c.push({type:6,index:a}),i.removeAttribute(e));if(_e.test(i.tagName)){let e=i.textContent.split(y),t=e.length-1;if(t>0){i.textContent=v?v.emptyScript:``;for(let n=0;n<t;n++)i.append(e[n],x()),A.nextNode(),c.push({type:2,index:++a});i.append(e[t],x())}}}else if(i.nodeType===8){if(i.data===ue)c.push({type:2,index:a});else{let e=-1;for(;(e=i.data.indexOf(y,e+1))!==-1;)c.push({type:7,index:a}),e+=y.length-1}}a++}}static createElement(e,t){let n=b.createElement(`template`);return n.innerHTML=e,n}};function M(e,t,n=e,r){if(t===O)return t;let i=r===void 0?n._$Cl:n._$Co?.[r],a=S(t)?void 0:t._$litDirective$;return i?.constructor!==a&&(i?._$AO?.(!1),a===void 0?i=void 0:(i=new a(e),i._$AT(e,n,r)),r===void 0?n._$Cl=i:(n._$Co??=[])[r]=i),i!==void 0&&(t=M(e,i._$AS(e,t.values),i,r)),t}var xe=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:n}=this._$AD,r=(e?.creationScope??b).importNode(t,!0);A.currentNode=r;let i=A.nextNode(),a=0,o=0,s=n[0];for(;s!==void 0;){if(a===s.index){let t;s.type===2?t=new N(i,i.nextSibling,this,e):s.type===1?t=new s.ctor(i,s.name,s.strings,this,e):s.type===6&&(t=new Te(i,this,e)),this._$AV.push(t),s=n[++o]}a!==s?.index&&(i=A.nextNode(),a++)}return A.currentNode=b,r}p(e){let t=0;for(let n of this._$AV)n!==void 0&&(n.strings===void 0?n._$AI(e[t]):(n._$AI(e,n,t),t+=n.strings.length-2)),t++}},N=class e{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,n,r){this.type=2,this._$AH=k,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=n,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=M(this,e,t),S(e)?e===k||e==null||e===``?(this._$AH!==k&&this._$AR(),this._$AH=k):e!==this._$AH&&e!==O&&this._(e):e._$litType$===void 0?e.nodeType===void 0?fe(e)?this.k(e):this._(e):this.T(e):this.$(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==k&&S(this._$AH)?this._$AA.nextSibling.data=e:this.T(b.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:n}=e,r=typeof n==`number`?this._$AC(e):(n.el===void 0&&(n.el=j.createElement(ye(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===r)this._$AH.p(t);else{let e=new xe(r,this),n=e.u(this.options);e.p(t),this.T(n),this._$AH=e}}_$AC(e){let t=ve.get(e.strings);return t===void 0&&ve.set(e.strings,t=new j(e)),t}k(t){C(this._$AH)||(this._$AH=[],this._$AR());let n=this._$AH,r,i=0;for(let a of t)i===n.length?n.push(r=new e(this.O(x()),this.O(x()),this,this.options)):r=n[i],r._$AI(a),i++;i<n.length&&(this._$AR(r&&r._$AB.nextSibling,i),n.length=i)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let t=se(e).nextSibling;se(e).remove(),e=t}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},P=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,n,r,i){this.type=1,this._$AH=k,this._$AN=void 0,this.element=e,this.name=t,this._$AM=r,this.options=i,n.length>2||n[0]!==``||n[1]!==``?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=k}_$AI(e,t=this,n,r){let i=this.strings,a=!1;if(i===void 0)e=M(this,e,t,0),a=!S(e)||e!==this._$AH&&e!==O,a&&(this._$AH=e);else{let r=e,o,s;for(e=i[0],o=0;o<i.length-1;o++)s=M(this,r[n+o],t,o),s===O&&(s=this._$AH[o]),a||=!S(s)||s!==this._$AH[o],s===k?e=k:e!==k&&(e+=(s??``)+i[o+1]),this._$AH[o]=s}a&&!r&&this.j(e)}j(e){e===k?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??``)}},Se=class extends P{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===k?void 0:e}},Ce=class extends P{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==k)}},we=class extends P{constructor(e,t,n,r,i){super(e,t,n,r,i),this.type=5}_$AI(e,t=this){if((e=M(this,e,t,0)??k)===O)return;let n=this._$AH,r=e===k&&n!==k||e.capture!==n.capture||e.once!==n.once||e.passive!==n.passive,i=e!==k&&(n===k||r);r&&this.element.removeEventListener(this.name,this,n),i&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH==`function`?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},Te=class{constructor(e,t,n){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(e){M(this,e)}},Ee=_.litHtmlPolyfillSupport;Ee?.(j,N),(_.litHtmlVersions??=[]).push(`3.3.3`);var De=(e,t,n)=>{let r=n?.renderBefore??t,i=r._$litPart$;if(i===void 0){let e=n?.renderBefore??null;r._$litPart$=i=new N(t.insertBefore(x(),e),e,void 0,n??{})}return i._$AI(e),i},F=globalThis,I=class extends g{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=De(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return O}};I._$litElement$=!0,I.finalized=!0,F.litElementHydrateSupport?.({LitElement:I});var Oe=F.litElementPolyfillSupport;Oe?.({LitElement:I}),(F.litElementVersions??=[]).push(`4.2.2`);var L=e=>(t,n)=>{n===void 0?customElements.define(e,t):n.addInitializer(()=>{customElements.define(e,t)})},ke={attribute:!0,type:String,converter:m,reflect:!1,hasChanged:h},Ae=(e=ke,t,n)=>{let{kind:r,metadata:i}=n,a=globalThis.litPropertyMetadata.get(i);if(a===void 0&&globalThis.litPropertyMetadata.set(i,a=new Map),r===`setter`&&((e=Object.create(e)).wrapped=!0),a.set(n.name,e),r===`accessor`){let{name:r}=n;return{set(n){let i=t.get.call(this);t.set.call(this,n),this.requestUpdate(r,i,e,!0,n)},init(t){return t!==void 0&&this.C(r,void 0,e,t),t}}}if(r===`setter`){let{name:r}=n;return function(n){let i=this[r];t.call(this,n),this.requestUpdate(r,i,e,!0,n)}}throw Error(`Unsupported decorator location: `+r)};function R(e){return(t,n)=>typeof n==`object`?Ae(e,t,n):((e,t,n)=>{let r=t.hasOwnProperty(n);return t.constructor.createProperty(n,e),r?Object.getOwnPropertyDescriptor(t,n):void 0})(e,t,n)}function z(e){return R({...e,state:!0,attribute:!1})}var je=`/api/v1`,B=class extends Error{constructor(e,t,n){super(n),this.name=`ApiError`,this.status=e,this.code=t}};async function Me(e){let t={};try{t=await e.json()}catch{}if(!e.ok){let n=typeof t.error==`string`?t.error:`http_error`,r=typeof t.message==`string`?t.message:`HTTP ${e.status}`;throw new B(e.status,n,r)}return t}var Ne=class{constructor(){this.csrfToken=null}setCsrfToken(e){this.csrfToken=e}async request(e,t={}){let n=new Headers(t.headers);return n.set(`Accept`,`application/json`),this.csrfToken&&t.method&&![`GET`,`HEAD`,`OPTIONS`].includes(t.method.toUpperCase())&&n.set(`X-CSRF-Token`,this.csrfToken),Me(await fetch(`${je}${e}`,{...t,headers:n,credentials:`same-origin`}))}async authStatus(){let e=await this.request(`/auth/status`);return this.setCsrfToken(e.csrfToken),e}async login(e){let t=await this.request(`/auth/login`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({password:e})});return this.setCsrfToken(t.csrfToken),t}async loadSnapshot(){let[e,t,n]=await Promise.all([this.request(`/state`),this.request(`/telemetry`),this.request(`/device`)]);return{revision:e.revision,state:e.state,telemetry:t,device:n}}async loadSensors(){return this.request(`/sensors`)}async patchState(e,t,n){return this.request(`/${e}`,{method:`PATCH`,headers:{"Content-Type":`application/json`,"If-Match":String(t)},body:JSON.stringify({revision:t,...n})})}};function Pe(e){let t=null,n=[];for(let r of e.split(`
`))if(r.startsWith(`id:`)){let e=Number.parseInt(r.slice(3).trim(),10);Number.isSafeInteger(e)&&e>=0&&(t=e)}else r.startsWith(`data:`)&&n.push(r.slice(5).trimStart());if(t===null||n.length===0)return null;let r=JSON.parse(n.join(`
`));return{id:t,snapshot:r}}var Fe=class{connect(e,t,n){let r=new AbortController;return this.pump(r,e,t).catch(e=>{r.signal.aborted||n(e)}),{close:()=>r.abort()}}async pump(e,t,n){let r=new Headers({Accept:`text/event-stream`});t!==null&&r.set(`Last-Event-ID`,String(t));let i=await fetch(`${je}/events`,{credentials:`same-origin`,headers:r,signal:e.signal,cache:`no-store`});if(!i.ok){await Me(i);return}if(!i.body)throw Error(`Сервер не открыл поток событий`);let a=i.body.getReader(),o=new TextDecoder,s=``;for(;!e.signal.aborted;){let{done:e,value:t}=await a.read();if(e)break;s+=o.decode(t,{stream:!0}).replace(/\r\n/g,`
`);let r=s.indexOf(`

`);for(;r>=0;){let e=Pe(s.slice(0,r));s=s.slice(r+2),e&&n(e.id,e.snapshot),r=s.indexOf(`

`)}}if(!e.signal.aborted)throw Error(`Поток событий закрыт сервером`)}},V=e=>{if(typeof e==`object`&&e&&!Object.isFrozen(e)){for(let t of Object.values(e))V(t);Object.freeze(e)}return e},Ie=()=>({phase:`loading`,auth:null,csrfToken:null,snapshot:null,error:null,connected:!1,lastEventId:0,retryDelay:500,sensors:[],mutationError:null}),H=e=>e instanceof Error?e.message:`Неизвестная ошибка`,Le=class{constructor(e,t,n=(e,t)=>window.setTimeout(e,t),r=e=>window.clearTimeout(e)){this.api=e,this.events=t,this.schedule=n,this.cancelSchedule=r,this.state=V(Ie()),this.listeners=new Set,this.connection=null,this.retryToken=0,this.stopped=!1,this.sessionTimer=null,this.sessionGeneration=0}get value(){return this.state}subscribe(e){return this.listeners.add(e),e(this.state),()=>this.listeners.delete(e)}update(e){this.state=V({...this.state,...e});for(let e of this.listeners)e(this.state)}async start(){this.stopped=!1,this.clearSessionExpiry(),this.connection?.close(),this.connection=null,this.update({phase:`loading`,error:null,connected:!1});try{let e=await this.api.authStatus(),t=this.applyAuth(e);if(e.required&&!e.authenticated){this.update({phase:`login`});return}if(!t)return;await this.loadAndConnect(this.sessionGeneration)}catch(e){this.handleLoadError(e)}}stop(){this.stopped=!0,this.retryToken+=1,this.clearSessionExpiry(),this.connection?.close(),this.connection=null,this.update({connected:!1})}async login(e){this.update({error:null});try{let t=await this.api.login(e);if(!this.applyAuth(t))return;this.update({phase:`loading`}),await this.loadAndConnect(this.sessionGeneration)}catch(e){this.handleLoadError(e,!0)}}async ensureSensors(){if(!((this.state.sensors?.length??0)>0||!this.api.loadSensors))try{let e=await this.api.loadSensors();this.update({sensors:e.sensors,mutationError:e.error})}catch(e){this.update({mutationError:`Не удалось загрузить датчики: ${H(e)}`})}}async patchScreen(e,t){if(!this.api.patchState||!this.state.snapshot){let e=`Редактор ещё не получил текущее состояние`;return this.update({mutationError:e}),{ok:!1,conflict:!1,error:e}}let n=this.state.snapshot.revision;try{let r=await this.api.patchState(e,n,t),i=await this.api.loadSnapshot();if(!r.saved||!r.queued||r.error){let e=r.error||`Состояние сохранено, но команда не поставлена в очередь`;return this.update({snapshot:i,mutationError:e}),{ok:!1,conflict:!1,error:e}}return this.update({snapshot:i,mutationError:null,error:null}),{ok:!0,conflict:!1,error:null}}catch(e){if(e instanceof B&&e.status===409){let e=this.state.snapshot;try{e=await this.api.loadSnapshot()}catch{}return this.update({snapshot:e,mutationError:`Конфликт ревизий: загружено актуальное состояние`}),{ok:!1,conflict:!0,error:`Конфликт ревизий: загружено актуальное состояние`}}let t=`Изменение не применено: ${H(e)}`;return this.update({mutationError:t}),{ok:!1,conflict:!1,error:t}}}async loadAndConnect(e){let t=await this.api.loadSnapshot();this.stopped||e!==this.sessionGeneration||(this.update({phase:`ready`,snapshot:t,error:null}),this.openEvents())}handleLoadError(e,t=!1){e instanceof B&&e.status===401?(this.clearSessionExpiry(),this.connection?.close(),this.connection=null,this.update({phase:`login`,connected:!1,error:H(e),auth:{required:!0,authenticated:!1,csrfToken:null},csrfToken:null})):this.update({phase:t?`login`:`error`,connected:!1,error:H(e)})}applyAuth(e){if(this.clearSessionExpiry(),this.api.setCsrfToken?.(e.csrfToken),this.update({auth:e,csrfToken:e.csrfToken}),!e.required||!e.authenticated)return!0;let t=e.expiresIn;if(typeof t!=`number`||!Number.isFinite(t)||t<=0)return this.expireSession(this.sessionGeneration),!1;let n=this.sessionGeneration;return this.sessionTimer=this.schedule(()=>this.expireSession(n),t*1e3),!0}clearSessionExpiry(){this.sessionGeneration+=1,this.sessionTimer!==null&&this.cancelSchedule(this.sessionTimer),this.sessionTimer=null}expireSession(e){this.stopped||e!==this.sessionGeneration||(this.sessionGeneration+=1,this.sessionTimer=null,this.retryToken+=1,this.connection?.close(),this.connection=null,this.api.setCsrfToken?.(null),this.update({phase:`login`,auth:{required:!0,authenticated:!1,csrfToken:null,expiresIn:0},csrfToken:null,connected:!1,error:`Сессия истекла. Войдите снова.`}))}openEvents(){if(this.stopped)return;this.connection?.close();let e=this.state.lastEventId>0?this.state.lastEventId:null;this.connection=this.events.connect(e,(e,t)=>this.acceptEvent(e,t),e=>this.handleEventError(e))}acceptEvent(e,t){!Number.isSafeInteger(e)||e<=this.state.lastEventId||this.state.snapshot&&t.revision<this.state.snapshot.revision||this.update({phase:`ready`,snapshot:t,error:null,connected:!0,lastEventId:e,retryDelay:500})}handleEventError(e){if(this.connection?.close(),this.connection=null,e instanceof B&&e.status===401){this.handleLoadError(e);return}let t=this.state.retryDelay;this.update({connected:!1,error:H(e),retryDelay:Math.min(t*2,1e4)});let n=++this.retryToken;this.schedule(()=>{!this.stopped&&n===this.retryToken&&this.openEvents()},t)}};function U(e,t,n,r){var i=arguments.length,a=i<3?t:r===null?r=Object.getOwnPropertyDescriptor(t,n):r,o;if(typeof Reflect==`object`&&typeof Reflect.decorate==`function`)a=Reflect.decorate(e,t,n,r);else for(var s=e.length-1;s>=0;s--)(o=e[s])&&(a=(i<3?o(a):i>3?o(t,n,a):o(t,n))||a);return i>3&&a&&Object.defineProperty(t,n,a),a}var Re={"cpu.temperature":`CPU`,"cpu.power":`CPU Power`,"gpu.temperature":`GPU`,"gpu.vram.used":`VRAM`,"gpu.power":`GPU Power`,"fan.cpu":`CPU Fan`,"fan.gpu":`GPU Fan`},W=e=>Number.isInteger(e)?String(e):e.toFixed(1),ze=e=>{if(!e.available||e.value===null)return`Недоступно`;let t=e.value;return e.unit===`B`||e.unit===`bytes`?`${(t/1024**3).toFixed(1)} GiB`:e.unit===`C`?`${W(t)} °C`:e.unit===`F`?`${W(t)} °F`:`${W(t)} ${e.unit}`.trim()},Be=(e=0)=>`${Math.floor(e/3600)}ч ${Math.floor(e%3600/60)}м`,G=class extends I{static{this.styles=o`
    :host { display: block; color: var(--ink, #f5f7fb); }
    .notice { margin: 0 0 1rem; padding: .8rem 1rem; border: 1px solid #eb5c9a66; border-radius: .8rem; background: #eb5c9a16; color: #ffc8df; }
    .loading { min-height: 40vh; display: grid; place-items: center; color: #a9b3c4; letter-spacing: .08em; text-transform: uppercase; }
    .error-state { min-height: 40vh; display: grid; place-content: center; gap: .6rem; text-align: center; }
    .error-state h1 { color: #ffc2d8; }
    .error-state p { color: #a9b3c4; }
    .hero { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(15rem, .65fr); gap: 1rem; margin-bottom: 1rem; }
    .panel { border: 1px solid #ffffff12; border-radius: 1rem; padding: 1.2rem; background: linear-gradient(145deg, #171b27e8, #0e111aee); box-shadow: 0 1rem 3rem #0006; }
    .device { position: relative; overflow: hidden; }
    .device::after { content: ""; position: absolute; inset: auto -10% -65% 45%; aspect-ratio: 1; border-radius: 50%; background: radial-gradient(circle, #54e8d64a, transparent 65%); pointer-events: none; }
    .eyebrow { color: #65e5d7; text-transform: uppercase; letter-spacing: .14em; font-size: .72rem; font-weight: 700; }
    h1, h2, p { margin: 0; }
    h1 { margin-top: .45rem; font-size: clamp(1.6rem, 3vw, 2.7rem); line-height: 1; }
    h2 { margin-bottom: 1rem; font-size: 1rem; color: #c7cfdb; }
    .status { display: inline-flex; align-items: center; gap: .45rem; margin-top: .8rem; color: #b9c5d6; }
    .dot { width: .55rem; height: .55rem; border-radius: 50%; background: #5de3b1; box-shadow: 0 0 1rem #5de3b1; }
    .dot.offline { background: #f2647f; box-shadow: 0 0 1rem #f2647f; }
    dl { display: grid; grid-template-columns: 1fr auto; gap: .55rem 1rem; margin: 0; }
    dt { color: #8591a5; }
    dd { margin: 0; text-align: right; font-variant-numeric: tabular-nums; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(11.5rem, 1fr)); gap: .8rem; }
    .metric { min-height: 7.5rem; display: flex; flex-direction: column; justify-content: space-between; }
    .metric strong { font-size: 1.5rem; font-variant-numeric: tabular-nums; }
    .metric small { color: #8591a5; overflow-wrap: anywhere; }
    .unavailable strong { color: #f0a9c3; font-size: 1rem; }
    .screen { margin-top: 1rem; }
    .media { color: #dce4f0; overflow-wrap: anywhere; }
    @media (max-width: 720px) { .hero { grid-template-columns: 1fr; } .panel { padding: 1rem; } }
    @media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; transition: none !important; } }
  `}render(){let e=this.view?.snapshot;if(!e&&this.view?.phase===`error`)return D`
      <section class="panel error-state" role="alert">
        <h1>Не удалось загрузить Dashboard</h1>
        <p>${this.view.error||`API недоступен`}</p>
        <p>Повторите попытку или проверьте состояние службы ryuo-screen.</p>
      </section>
    `;if(!e)return D`<div class="loading" role="status">Загрузка телеметрии…</div>`;let{device:t,state:n,telemetry:r}=e;return D`
      ${this.view.error?D`<div class="notice" role="alert">${this.view.error}</div>`:k}
      <main aria-label="Сводка системы">
        <div class="hero">
          <section class="panel device" aria-label="Устройство">
            <span class="eyebrow">ROG Ryuo IV · Live</span>
            <h1>${t.model||`Ryuo IV`}</h1>
            <div class="status"><span class="dot ${t.connected?``:`offline`}"></span>${t.connected?`Подключено`:`Нет соединения`} · ${t.health}</div>
          </section>
          <section class="panel" aria-label="Состояние демона">
            <h2>Daemon / HID</h2>
            <dl>
              <dt>Firmware</dt><dd>${t.firmware||`—`}</dd>
              <dt>Uptime</dt><dd>${Be(t.uptime)}</dd>
              <dt>Last ACK</dt><dd>${t.last_ack??`—`}</dd>
              <dt>Reconnects</dt><dd>${t.reconnect_count??0}</dd>
            </dl>
          </section>
        </div>
        <section aria-label="Телеметрия">
          <h2>Live telemetry</h2>
          <div class="grid">
            ${Object.entries(r.measurements).map(([e,t])=>D`
              <article class="panel metric ${t.available?``:`unavailable`}">
                <span class="eyebrow">${Re[e]||e}</span>
                <strong>${ze(t)}</strong>
                <small>${t.available?t.source||`Источник не указан`:t.error||`Нет данных от датчика`}</small>
              </article>
            `)}
          </div>
        </section>
        <section class="panel screen" aria-label="Текущая конфигурация экрана">
          <h2>Screen state</h2>
          <dl>
            <dt>Profile</dt><dd>${n.active_profile||`Без профиля`}</dd>
            <dt>Layout</dt><dd>${n.screen_mode}</dd>
            <dt>Brightness</dt><dd>${n.brightness}%</dd>
            <dt>Media</dt><dd class="media">${n.media.flat().join(` · `)||`Не выбрано`}</dd>
          </dl>
        </section>
      </main>
    `}};U([R({attribute:!1})],G.prototype,`view`,void 0),G=U([L(`dashboard-page`)],G);var K=class extends I{static{this.styles=o`
    :host { display: block; min-height: 70vh; display: grid; place-items: center; color: #f5f7fb; }
    .card { width: min(24rem, calc(100vw - 2rem)); padding: 1.6rem; border: 1px solid #ffffff16; border-radius: 1.2rem; background: #121722e8; box-shadow: 0 1.5rem 4rem #0008; }
    .mark { color: #61e5d6; text-transform: uppercase; font-size: .72rem; font-weight: 800; letter-spacing: .15em; }
    h1 { margin: .55rem 0 .5rem; font-size: 1.8rem; }
    p { color: #98a4b6; line-height: 1.5; }
    label { display: grid; gap: .45rem; margin-top: 1.2rem; color: #cdd4df; }
    input { color: #fff; background: #080b12; border: 1px solid #ffffff24; border-radius: .7rem; padding: .8rem; font: inherit; }
    input:focus-visible, button:focus-visible { outline: 3px solid #66e5d7; outline-offset: 2px; }
    button { width: 100%; margin-top: .85rem; padding: .8rem; border: 0; border-radius: .7rem; color: #07110f; background: linear-gradient(90deg, #5ce4d3, #79f0b6); font: inherit; font-weight: 800; cursor: pointer; }
    [role=alert] { color: #ffc2d8; padding: .7rem; border-radius: .6rem; background: #f2558c18; }
  `}render(){return!this.view||this.view.phase!==`login`||!this.view.auth?.required?k:D`
      <section class="card" aria-labelledby="login-title">
        <span class="mark">Ryuo Control</span>
        <h1 id="login-title">Вход в LAN-панель</h1>
        <p>Пароль проверяется локальным сервисом и не сохраняется в интерфейсе.</p>
        ${this.view.error?D`<p role="alert">${this.view.error}</p>`:k}
        <form @submit=${this.submit}>
          <label>Пароль<input type="password" name="password" autocomplete="current-password" required></label>
          <button type="submit">Войти</button>
        </form>
      </section>
    `}submit(e){e.preventDefault();let t=e.currentTarget.elements.namedItem(`password`),n=t.value;t.value=``,this.dispatchEvent(new CustomEvent(`login-submit`,{detail:{password:n},bubbles:!0,composed:!0}))}};U([R({attribute:!1})],K.prototype,`view`,void 0),K=U([L(`login-view`)],K);var Ve=()=>({enabled:!1,measurement_id:``,widget:``,label:null}),He=e=>({...e}),q=e=>{if(e.length>6)throw RangeError(`screen editor supports exactly six slots`);let t=e.map(He);for(;t.length<6;)t.push(Ve());return t},Ue=(e,t,n)=>{let r=q(e);if(!Number.isInteger(t)||!Number.isInteger(n)||t<0||t>=6||n<0||n>=6)throw RangeError(`slot position must be between zero and five`);let[i]=r.splice(t,1);return r.splice(n,0,i),r},J=(e,t)=>e[0]??t,We=(e,t)=>t===`Screen Splitting`?{...e,screen_mode:t,media:[[...e.media[0]??[]],[...e.media[1]??[]]],playback_modes:[J(e.playback_modes,`Single`),e.playback_modes[1]??`Single`],title_colors:[J(e.title_colors,`#E5252B`),e.title_colors[1]??J(e.title_colors,`#E5252B`)],content_colors:[J(e.content_colors,`#FFFFFF`),e.content_colors[1]??J(e.content_colors,`#FFFFFF`)]}:{...e,screen_mode:`Full Screen`,media:[[...e.media[0]??[]]],playback_modes:[J(e.playback_modes,`Single`)],title_colors:[J(e.title_colors,`#E5252B`)],content_colors:[J(e.content_colors,`#FFFFFF`)]},Ge=Object.freeze({"cpu.load":`CPU Load`,"cpu.usage":`CPU Usage`,"cpu.temperature":`CPU Temperature`,"cpu.frequency":`CPU Speed Average`,"cpu.voltage":`CPU Voltage`,"gpu.load":`GPU Load`,"gpu.usage":`GPU Usage`,"gpu.temperature":`GPU Temperature`,"gpu.clock.core":`GPU Speed`,"gpu.power":`GPU Power`,"gpu.voltage":`GPU Voltage`,"memory.load":`Memory Utilization`,"memory.frequency":`Memory Frequency`,"disk.temperature":`Hard Disk Temperature`,"motherboard.temperature":`Motherboard Temperature`}),Ke=e=>e.flatMap(e=>{let t=e.measurementId.startsWith(`fan.`)&&e.unit===`RPM`,n=t?`Fan Speed ${e.label}`:Ge[e.measurementId];return n?[{descriptor:e,widget:n,available:e.available,userLabelCapable:t}]:[]}),qe=e=>({...e,media:e.media.map(e=>[...e]),playback_modes:[...e.playback_modes],slots:q(e.slots),title_colors:[...e.title_colors],content_colors:[...e.content_colors],sensor_selectors:{...e.sensor_selectors}}),Y=class extends I{static{this.styles=o`
    :host { display: block; }
    figure { margin: 0; display: grid; gap: .65rem; }
    figcaption { color: #aeb9c9; font-size: .78rem; }
    .panel { aspect-ratio: 2240 / 1080; display: grid; grid-template-columns: 1fr; overflow: hidden; border: .55rem solid #202838; border-radius: 1.2rem; background: #070a11; box-shadow: inset 0 0 3rem #000, 0 1rem 2.5rem #0005; opacity: calc(var(--preview-opacity, 100) / 100); }
    .panel.split { grid-template-columns: 1fr 1fr; }
    .zone { display: grid; grid-template-columns: repeat(3, 1fr); gap: .35rem; padding: .7rem; border-right: 1px solid #ffffff18; background: radial-gradient(circle at 25% 0%, #153f4c, transparent 60%); }
    .slot { display: grid; place-content: center; min-width: 0; padding: .3rem; border-radius: .45rem; background: #111827c9; color: #fff; text-align: center; font-size: clamp(.5rem, 1.2vw, .78rem); overflow-wrap: anywhere; }
    .slot.off { opacity: .25; }
  `}render(){if(!this.state)return D``;let e=this.state.screen_mode===`Screen Splitting`,t=e?[this.state.slots.slice(0,3),this.state.slots.slice(3,6)]:[this.state.slots];return D`
      <figure aria-label="Предпросмотр расположения виджетов">
        <div class="panel ${e?`split`:``}" style=${`--preview-opacity:${this.state.opacity}`}>
          ${t.map(e=>D`<div class="zone">
            ${e.map(e=>D`<div class="slot ${e.enabled?``:`off`}">${e.enabled?e.label||e.widget:`Пусто`}</div>`)}
          </div>`)}
        </div>
        <figcaption>Предпросмотр конфигурации — не снимок экрана</figcaption>
      </figure>
    `}};U([R({attribute:!1})],Y.prototype,`state`,void 0),Y=U([L(`device-preview`)],Y);var X=32,Z=class extends I{constructor(...e){super(...e),this.assignment={enabled:!1,measurement_id:``,widget:``,label:null},this.options=[],this.index=0}static{this.styles=o`
    :host { display: block; }
    article { display: grid; gap: .55rem; padding: .8rem; border: 1px solid #ffffff16; border-radius: .8rem; background: #0c111bd9; }
    header { display: flex; align-items: center; justify-content: space-between; gap: .5rem; }
    strong { color: #67e5d7; }
    .moves { display: flex; gap: .3rem; }
    button, select, input { font: inherit; color: #eef4fb; background: #151c29; border: 1px solid #ffffff24; border-radius: .45rem; padding: .45rem; }
    button { min-width: 2rem; cursor: pointer; }
    button:focus-visible, select:focus-visible, input:focus-visible { outline: 2px solid #65e5d7; outline-offset: 2px; }
    label { display: grid; gap: .25rem; color: #a9b4c6; font-size: .82rem; }
    .meta { display: grid; gap: .2rem; color: #8f9bad; font-size: .72rem; overflow-wrap: anywhere; }
    .bad { color: #f2a8c2; }
  `}render(){let e=this.options.find(e=>e.descriptor.measurementId===this.assignment.measurement_id);return D`
      <article draggable="true" @dragstart=${this.onDragStart} @dragover=${this.onDragOver} @drop=${this.onDrop}>
        <header>
          <strong>Слот ${this.index+1}</strong>
          <span class="moves">
            <button type="button" aria-label="Переместить слот ${this.index+1} вверх" ?disabled=${this.index===0} @click=${()=>this.move(-1)}>↑</button>
            <button type="button" aria-label="Переместить слот ${this.index+1} вниз" ?disabled=${this.index===5} @click=${()=>this.move(1)}>↓</button>
          </span>
        </header>
        <label>Датчик
          <select .value=${this.assignment.enabled?this.assignment.measurement_id:``} @change=${this.onSensorChange}>
            <option value="">Отключён — позиция сохранена</option>
            ${this.options.map(e=>D`
              <option value=${e.descriptor.measurementId}>
                ${e.descriptor.label} · ${e.descriptor.ref.provider} · ${e.available?`доступен`:`недоступен`}
              </option>
            `)}
          </select>
        </label>
        ${e?.userLabelCapable?D`
          <label>Пользовательская подпись
            <input name="slot_label" maxlength="32" .value=${this.assignment.label??e.descriptor.label} @change=${this.onLabelChange}>
          </label>
        `:k}
        ${e?D`
          <div class="meta ${e.available?``:`bad`}">
            <span>${e.descriptor.ref.provider} / ${e.descriptor.ref.device}</span>
            <span>${e.descriptor.source||`Источник не указан`}</span>
            ${e.available?k:D`<span>${e.descriptor.error||`Датчик недоступен`}</span>`}
          </div>
        `:k}
      </article>
    `}emit(e,t){this.dispatchEvent(new CustomEvent(e,{detail:t,bubbles:!0,composed:!0}))}move(e){this.emit(`slot-move`,{from:this.index,to:this.index+e})}onDragStart(e){e.dataTransfer?.setData(`text/plain`,String(this.index)),e.dataTransfer&&(e.dataTransfer.effectAllowed=`move`),this.emit(`slot-drag-start`,{index:this.index})}onDragOver(e){e.preventDefault(),e.dataTransfer&&(e.dataTransfer.dropEffect=`move`)}onDrop(e){e.preventDefault(),this.emit(`slot-drop`,{index:this.index})}onSensorChange(e){let t=e.currentTarget.value;if(!t){this.emit(`slot-change`,{index:this.index,assignment:{...this.assignment,enabled:!1}});return}let n=this.options.find(e=>e.descriptor.measurementId===t);if(!n)return;let r=n.descriptor.label.slice(0,X);this.emit(`slot-change`,{index:this.index,assignment:{enabled:!0,measurement_id:t,widget:n.widget,label:n.userLabelCapable?r:null}})}onLabelChange(e){let t=e.currentTarget.value.trim().slice(0,X),n=this.options.find(e=>e.descriptor.measurementId===this.assignment.measurement_id);if(!n?.userLabelCapable)return;let r=n.descriptor.label.slice(0,X);this.emit(`slot-change`,{index:this.index,assignment:{...this.assignment,label:t||r,widget:`Fan Speed ${t||r}`}})}};U([R({attribute:!1})],Z.prototype,`assignment`,void 0),U([R({attribute:!1})],Z.prototype,`options`,void 0),U([R({type:Number})],Z.prototype,`index`,void 0),Z=U([L(`sensor-slot`)],Z);var Je=()=>({schema_version:1,revision:0,active_profile:null,screen_mode:`Full Screen`,media:[[]],playback_modes:[`Single`],slots:q([]),brightness:85,temperature_unit:`Celsius`,refresh_interval:1,title_colors:[`#E5252B`],content_colors:[`#FFFFFF`],opacity:100,rgb_mode:`off`,rgb_target:`value`,thermal_source:`cpu.temperature`,sensor_selectors:{}}),Q=class extends I{constructor(...e){super(...e),this.snapshot=null,this.sensors=[],this.mutationError=null,this.draft=Je(),this.fullRestart=!1,this.dragFrom=null,this.draftRevision=-1,this.patchTimer=null,this.pending=new Map}static{this.styles=o`
    :host { display: block; color: #f5f7fb; }
    .page { display: grid; gap: 1rem; }
    .heading { display: flex; justify-content: space-between; gap: 1rem; align-items: end; }
    h1, h2, p { margin: 0; }
    h1 { font-size: clamp(1.5rem, 3vw, 2.4rem); }
    .muted { color: #91a0b5; }
    .layout { display: grid; grid-template-columns: minmax(19rem, .9fr) minmax(24rem, 1.35fr); gap: 1rem; align-items: start; }
    .panel { border: 1px solid #ffffff14; border-radius: 1rem; padding: 1rem; background: linear-gradient(145deg, #151a27eb, #0d111aee); box-shadow: 0 1rem 2.5rem #0004; }
    .preview { position: sticky; top: 5.5rem; display: grid; gap: 1rem; }
    .controls { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .8rem; }
    fieldset { grid-column: 1 / -1; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .7rem; margin: 0; padding: .8rem; border: 1px solid #ffffff16; border-radius: .8rem; }
    legend { padding: 0 .35rem; color: #67e5d7; }
    label { display: grid; gap: .3rem; color: #aeb9c9; font-size: .82rem; }
    input, select { width: 100%; min-width: 0; padding: .55rem; border: 1px solid #ffffff24; border-radius: .5rem; color: #f5f7fb; background: #111827; font: inherit; }
    input[type="color"] { min-height: 2.65rem; padding: .25rem; }
    input:focus-visible, select:focus-visible { outline: 2px solid #65e5d7; outline-offset: 2px; }
    .slots { display: grid; gap: .65rem; margin-top: .8rem; }
    .alert { padding: .75rem .9rem; border: 1px solid #f26ca066; border-radius: .7rem; color: #ffc8df; background: #ed5d9214; }
    .restart { border-color: #f1b35b66; color: #ffd9a1; background: #e99b3112; }
    @media (max-width: 880px) { .layout { grid-template-columns: 1fr; } .preview { position: static; } }
    @media (max-width: 560px) { .controls, fieldset { grid-template-columns: 1fr; } .heading { align-items: start; flex-direction: column; } }
  `}connectedCallback(){super.connectedCallback(),this.controller?.ensureSensors()}disconnectedCallback(){this.patchTimer!==null&&window.clearTimeout(this.patchTimer),this.patchTimer=null,this.pending.clear(),super.disconnectedCallback()}willUpdate(e){e.has(`snapshot`)&&this.snapshot&&this.snapshot.state.revision!==this.draftRevision&&(this.draft=qe(this.snapshot.state),this.draftRevision=this.snapshot.state.revision,this.fullRestart=!1)}render(){let e=Ke(this.sensors),t=this.draft.screen_mode===`Screen Splitting`?2:1;return D`
      <section class="page" aria-labelledby="screen-heading">
        <div class="heading">
          <div>
            <p class="muted">Ryuo IV · Screen composer</p>
            <h1 id="screen-heading">Экран и шесть слотов</h1>
          </div>
          <p class="muted">Revision ${this.draft.revision}</p>
        </div>
        ${this.mutationError?D`<div class="alert" role="alert">${this.mutationError}</div>`:k}
        ${this.fullRestart?D`<div class="alert restart" data-full-restart>Изменение media или режима перезапустит воспроизведение полной конфигурацией.</div>`:k}
        <div class="layout">
          <aside class="panel preview" aria-label="Предпросмотр">
            <p class="muted">Предпросмотр конфигурации — не снимок экрана</p>
            <device-preview .state=${this.draft}></device-preview>
            <div class="controls">
              <label>Режим экрана
                <select name="screen_mode" .value=${this.draft.screen_mode} @change=${this.onMode}>
                  <option>Full Screen</option><option>Screen Splitting</option>
                </select>
              </label>
              <label>Яркость
                <input name="brightness" type="range" min="0" max="102" step="1" .value=${String(this.draft.brightness)} @input=${this.onBrightness}>
              </label>
              <label>Единица температуры
                <select name="temperature_unit" .value=${this.draft.temperature_unit} @change=${this.onUnit}>
                  <option>Celsius</option><option>Fahrenheit</option>
                </select>
              </label>
              <label>Интервал, сек
                <input name="refresh_interval" type="number" min="0.1" max="60" step="0.1" .value=${String(this.draft.refresh_interval)} @change=${this.onInterval}>
              </label>
              <label>Прозрачность
                <input name="opacity" type="range" min="0" max="100" step="1" .value=${String(this.draft.opacity)} @input=${this.onOpacity}>
              </label>
              <label>RGB режим
                <select name="rgb_mode" .value=${this.draft.rgb_mode} @change=${this.onRgbMode}>
                  <option value="off">Off</option><option value="hue">Hue</option><option value="thermal">Thermal</option>
                </select>
              </label>
              <label>RGB цель
                <select name="rgb_target" .value=${this.draft.rgb_target} @change=${this.onRgbTarget}>
                  <option value="title">Title</option><option value="value">Value</option><option value="both">Both</option>
                </select>
              </label>
              <label>Thermal source
                <select name="thermal_source" .value=${this.draft.thermal_source} @change=${this.onThermalSource}>
                  ${e.filter(e=>e.descriptor.unit===`°C`||e.descriptor.unit===`C`).map(e=>D`
                    <option value=${e.descriptor.measurementId}>${e.descriptor.label}</option>
                  `)}
                </select>
              </label>
              <fieldset>
                <legend>Цвета зон</legend>
                ${Array.from({length:t},(e,t)=>D`
                  <label>Заголовок ${t+1}<input type="color" name=${`title_color_${t}`} .value=${this.draft.title_colors[t]} @input=${e=>this.onColor(e,`title_colors`,t)}></label>
                  <label>Значение ${t+1}<input type="color" name=${`content_color_${t}`} .value=${this.draft.content_colors[t]} @input=${e=>this.onColor(e,`content_colors`,t)}></label>
                `)}
              </fieldset>
            </div>
          </aside>
          <section class="panel" aria-label="Редактор слотов">
            <h2>Позиции датчиков</h2>
            <p class="muted">Отключение сохраняет позицию. Перетаскивайте карточки или используйте кнопки со стрелками.</p>
            <p class="muted">${e.map(e=>`${e.descriptor.ref.provider}/${e.descriptor.ref.device}: ${e.available?`доступен`:e.descriptor.error||`недоступен`}`).join(` · `)}</p>
            <div class="slots" @slot-change=${this.onSlotChange} @slot-move=${this.onSlotMove} @slot-drag-start=${this.onSlotDragStart} @slot-drop=${this.onSlotDrop}>
              ${this.draft.slots.map((t,n)=>D`
                <sensor-slot
                  aria-label=${`Слот ${n+1}: ${t.enabled?t.label||t.widget:`отключён`}`}
                  .assignment=${t}
                  .options=${e}
                  .index=${n}>
                </sensor-slot>
              `)}
            </div>
          </section>
        </div>
      </section>
    `}queue(e,t){this.pending.set(e,{...this.pending.get(e)??{},...t}),this.patchTimer!==null&&window.clearTimeout(this.patchTimer),this.patchTimer=window.setTimeout(()=>{this.flush()},160)}async flush(){this.patchTimer=null;let e=[...this.pending.entries()];this.pending.clear();for(let[t,n]of e)if(!(await this.controller.patchScreen(t,n)).ok)break}onBrightness(e){let t=Number(e.currentTarget.value);this.draft={...this.draft,brightness:t},this.queue(`brightness`,{brightness:t})}onOpacity(e){let t=Number(e.currentTarget.value);this.draft={...this.draft,opacity:t},this.queue(`screen`,{opacity:t})}onUnit(e){let t=e.currentTarget.value;this.draft={...this.draft,temperature_unit:t},this.queue(`telemetry-settings`,{temperature_unit:t})}onInterval(e){let t=Number(e.currentTarget.value);t>0&&t<=60&&(this.draft={...this.draft,refresh_interval:t},this.queue(`telemetry-settings`,{refresh_interval:t}))}onMode(e){let t=e.currentTarget.value;this.draft=We(this.draft,t),this.fullRestart=!0,this.queue(`screen`,{screen_mode:this.draft.screen_mode,media:this.draft.media,playback_modes:this.draft.playback_modes,title_colors:this.draft.title_colors,content_colors:this.draft.content_colors})}onColor(e,t,n){let r=[...this.draft[t]];r[n]=e.currentTarget.value.toUpperCase(),this.draft={...this.draft,[t]:r},this.queue(`screen`,{[t]:r})}onRgbMode(e){let t=e.currentTarget.value;this.draft={...this.draft,rgb_mode:t},this.queue(`screen`,{rgb_mode:t})}onRgbTarget(e){let t=e.currentTarget.value;this.draft={...this.draft,rgb_target:t},this.queue(`screen`,{rgb_target:t})}onThermalSource(e){let t=e.currentTarget.value;this.draft={...this.draft,thermal_source:t},this.queue(`screen`,{thermal_source:t})}onSlotChange(e){let t=q(this.draft.slots);t[e.detail.index]={...e.detail.assignment},this.draft={...this.draft,slots:t},this.queue(`screen`,{slots:t})}onSlotMove(e){let t=Ue(this.draft.slots,e.detail.from,e.detail.to);this.draft={...this.draft,slots:t},this.queue(`screen`,{slots:t})}onSlotDragStart(e){this.dragFrom=e.detail.index}onSlotDrop(e){if(this.dragFrom===null)return;let t=this.dragFrom;this.dragFrom=null,this.onSlotMove(new CustomEvent(`slot-move`,{detail:{from:t,to:e.detail.index}}))}};U([R({attribute:!1})],Q.prototype,`snapshot`,void 0),U([R({attribute:!1})],Q.prototype,`sensors`,void 0),U([R({attribute:!1})],Q.prototype,`controller`,void 0),U([R({attribute:!1})],Q.prototype,`mutationError`,void 0),U([z()],Q.prototype,`draft`,void 0),U([z()],Q.prototype,`fullRestart`,void 0),Q=U([L(`screen-page`)],Q);var $=class extends I{constructor(...e){super(...e),this.store=new Le(new Ne,new Fe),this.view=this.store.value,this.page=`dashboard`}static{this.styles=o`
    :host { display: block; min-height: 100vh; }
    header { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 1rem clamp(1rem, 4vw, 3rem); border-bottom: 1px solid #ffffff10; background: #090c13dd; backdrop-filter: blur(14px); position: sticky; top: 0; z-index: 2; }
    .brand { display: flex; align-items: center; gap: .7rem; font-weight: 850; letter-spacing: .03em; }
    .glyph { display: grid; place-items: center; width: 2rem; aspect-ratio: 1; border-radius: .65rem; color: #07110f; background: linear-gradient(145deg, #5be3d3, #f265a1); }
    nav { display: flex; gap: .35rem; color: #99a6b9; font-size: .9rem; }
    nav button { padding: .4rem .55rem; border: 0; border-bottom: 2px solid transparent; color: #99a6b9; background: transparent; font: inherit; cursor: pointer; }
    nav button[aria-current="page"] { color: #f5f7fb; border-bottom-color: #5be3d3; }
    nav button:focus-visible { outline: 2px solid #5be3d3; outline-offset: 2px; }
    .stream { display: flex; align-items: center; gap: .45rem; color: #9da9ba; font-size: .8rem; }
    .stream::before { content: ""; width: .45rem; height: .45rem; border-radius: 50%; background: #f26c83; }
    .stream.live::before { background: #5de2b0; }
    main { width: min(78rem, calc(100% - 2rem)); margin: 1.2rem auto 3rem; }
    @media (max-width: 560px) { header { padding: .8rem 1rem; flex-wrap: wrap; } nav { order: 3; width: 100%; } nav button { flex: 1; } main { width: min(100% - 1rem, 78rem); } }
  `}connectedCallback(){super.connectedCallback(),this.unsubscribe=this.store.subscribe(e=>{this.view=e}),this.store.start()}disconnectedCallback(){this.unsubscribe?.(),this.store.stop(),super.disconnectedCallback()}render(){return D`
      <header>
        <div class="brand"><span class="glyph">IV</span> RYŪŌ SCREEN</div>
        <nav aria-label="Основная навигация">
          <button type="button" aria-current=${this.page===`dashboard`?`page`:`false`} @click=${()=>{this.page=`dashboard`}}>Dashboard</button>
          <button type="button" aria-current=${this.page===`screen`?`page`:`false`} @click=${()=>{this.page=`screen`}}>Экран</button>
        </nav>
        <div class="stream ${this.view.connected?`live`:``}">${this.view.connected?`Live`:`Offline`}</div>
      </header>
      <main>
        ${this.view.phase===`login`?D`<login-view .view=${this.view} @login-submit=${this.onLogin}></login-view>`:this.page===`screen`?D`<screen-page
                .snapshot=${this.view.snapshot}
                .sensors=${this.view.sensors??[]}
                .controller=${this.store}
                .mutationError=${this.view.mutationError??null}>
              </screen-page>`:D`<dashboard-page .view=${this.view}></dashboard-page>`}
      </main>
    `}onLogin(e){this.store.login(e.detail.password)}};U([R({attribute:!1})],$.prototype,`store`,void 0),U([z()],$.prototype,`view`,void 0),U([z()],$.prototype,`page`,void 0),$=U([L(`ryuo-app`)],$);