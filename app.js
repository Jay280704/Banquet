document.addEventListener('DOMContentLoaded', () => {

    // ==========================================
    // 1. STICKY HEADER & ACTIVE SCROLL LINK
    // ==========================================
    const header = document.getElementById('main-header');
    const sections = document.querySelectorAll('section');
    const navLinks = document.querySelectorAll('.nav-link');

    window.addEventListener('scroll', () => {
        // Sticky Header class toggle
        if (window.scrollY > 50) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }

        // Active section nav link highlight
        let current = '';
        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionHeight = section.clientHeight;
            if (pageYOffset >= (sectionTop - 150)) {
                current = section.getAttribute('id');
            }
        });

        navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('href') === `#${current}`) {
                link.classList.add('active');
            }
        });
    });

    // ==========================================
    // 2. MOBILE MENU DRAWER
    // ==========================================
    const menuToggle = document.getElementById('menu-toggle');
    const navMenu = document.getElementById('nav-menu');

    menuToggle.addEventListener('click', () => {
        menuToggle.classList.toggle('active');
        navMenu.classList.toggle('active');
    });

    // Close menu when clicking links
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            menuToggle.classList.remove('active');
            navMenu.classList.remove('active');
        });
    });

    // ==========================================
    // 3. DYNAMIC SHOWCASE GALLERY & FILTER
    // ==========================================
    const gridContainer = document.getElementById('showcase-grid');
    if (gridContainer) {
        fetch('/api/photos')
            .then(res => res.json())
            .then(photos => {
                gridContainer.innerHTML = '';
                
                const categoryTags = {
                    wedding: 'Banquet Hall',
                    community: 'Community Hall',
                    dining: 'Dining & Lounge',
                    terrace: 'Terrace Deck'
                };
                
                if (photos.length === 0) {
                    gridContainer.innerHTML = `
                        <div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: var(--text-muted-light); font-size: 1.1rem;">
                            No showcase photos available yet. Check back soon!
                        </div>`;
                    return;
                }
                
                photos.forEach(photo => {
                    const item = document.createElement('div');
                    item.className = 'showcase-item';
                    item.setAttribute('data-category', photo.category);
                    
                    item.innerHTML = `
                        <img class="showcase-img" src="${photo.image_path}" alt="${photo.title}">
                        <div class="showcase-overlay">
                            <span class="showcase-tag">${categoryTags[photo.category] || 'Showcase'}</span>
                            <h3>${photo.title}</h3>
                            <p>${photo.description || ''}</p>
                            ${photo.capacity ? `
                            <div class="showcase-capacity">
                                <svg viewBox="0 0 24 24">
                                    <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M8.5 10a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm11 11v-2a4 4 0 0 0-3-3.87m-4-12a4 4 0 0 1 0 7.75" />
                                </svg>
                                Capacity: ${photo.capacity}
                            </div>
                            ` : ''}
                        </div>
                    `;
                    gridContainer.appendChild(item);
                });
                
                // Initialize gallery filtering logic
                initializeFilterLogic();
            })
            .catch(err => {
                console.error('Error fetching showcase photos:', err);
                gridContainer.innerHTML = `
                    <div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: var(--text-muted-light); font-size: 1.1rem;">
                        Could not load the showcase gallery. Please refresh or try again.
                    </div>`;
            });
    }

    function initializeFilterLogic() {
        const filterButtons = document.querySelectorAll('.filter-btn');
        const showcaseItems = document.querySelectorAll('.showcase-item');

        filterButtons.forEach(button => {
            button.addEventListener('click', () => {
                // Remove active class from buttons
                filterButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');

                const filterValue = button.getAttribute('data-filter');

                showcaseItems.forEach(item => {
                    const category = item.getAttribute('data-category');
                    
                    if (filterValue === 'all' || category === filterValue) {
                        item.style.display = 'block';
                        setTimeout(() => {
                            item.style.opacity = '1';
                            item.style.transform = 'scale(1)';
                        }, 50);
                    } else {
                        item.style.opacity = '0';
                        item.style.transform = 'scale(0.85)';
                        setTimeout(() => {
                            item.style.display = 'none';
                        }, 400);
                    }
                });
            });
        });
    }

    // ==========================================
    // 4. INTERACTIVE BUDGET ESTIMATOR
    // ==========================================
    const eventRadios = document.querySelectorAll('input[name="estimator-event"]');
    const guestSlider = document.getElementById('guest-slider');
    const guestBubble = document.getElementById('guest-count-bubble');
    const cateringRadios = document.querySelectorAll('input[name="estimator-catering"]');
    const addonCheckboxes = document.querySelectorAll('input[name="estimator-addon"]');

    // Output fields
    const summaryBase = document.getElementById('summary-base');
    const summaryGuestCount = document.getElementById('summary-guest-count');
    const summaryCatering = document.getElementById('summary-catering');
    const summaryAddons = document.getElementById('summary-addons');
    const summaryTax = document.getElementById('summary-tax');
    const summaryTotal = document.getElementById('summary-total');

    // Pricing models definition
    const basePrices = {
        wedding: 75000,
        corporate: 45000,
        social: 25000
    };

    const cateringPrices = {
        classic: 450,
        elite: 650,
        imperial: 950
    };

    let totalAnimationTimer = null;

    function calculateEstimate() {
        // 1. Get Event Base Price
        let selectedEvent = 'wedding';
        eventRadios.forEach(radio => {
            if (radio.checked) selectedEvent = radio.value;
        });
        const basePrice = basePrices[selectedEvent];

        // 2. Get Guest Count
        const guests = parseInt(guestSlider.value);
        guestBubble.innerText = `${guests} Guests`;
        const percentage = (guests - 30) / (400 - 30);
        guestBubble.style.left = `calc(${percentage * 100}% - 35px)`;
        summaryGuestCount.innerText = guests;

        // 3. Get Catering Price
        let selectedCatering = 'classic';
        cateringRadios.forEach(radio => {
            if (radio.checked) selectedCatering = radio.value;
        });
        const cateringCost = cateringPrices[selectedCatering] * guests;

        // 4. Get Add-ons Cost
        let addonsCost = 0;
        addonCheckboxes.forEach(checkbox => {
            if (checkbox.checked) {
                addonsCost += parseInt(checkbox.getAttribute('data-price'));
            }
        });

        // 5. Calculate Taxes & Total
        const subtotal = basePrice + cateringCost + addonsCost;
        const taxCost = Math.round(subtotal * 0.18);
        const finalTotal = subtotal + taxCost;

        // Update Option Cards selection indicators (highlighting the label parent border)
        updateOptionHighlighting(eventRadios);
        updateOptionHighlighting(cateringRadios);
        updateCheckboxHighlighting();

        // Write outputs
        summaryBase.innerText = formatCurrency(basePrice);
        summaryCatering.innerText = formatCurrency(cateringCost);
        summaryAddons.innerText = formatCurrency(addonsCost);
        summaryTax.innerText = formatCurrency(taxCost);

        // Smooth Counter Animation for Final Total
        animatePriceCounter(finalTotal);
    }

    function updateOptionHighlighting(radios) {
        radios.forEach(radio => {
            const label = radio.closest('.option-card');
            if (radio.checked) {
                label.classList.add('selected');
            } else {
                label.classList.remove('selected');
            }
        });
    }

    function updateCheckboxHighlighting() {
        addonCheckboxes.forEach(checkbox => {
            const label = checkbox.closest('.option-card');
            if (checkbox.checked) {
                label.classList.add('selected');
            } else {
                label.classList.remove('selected');
            }
        });
    }

    function formatCurrency(amount) {
        return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(amount);
    }

    function animatePriceCounter(targetValue) {
        const duration = 800; // ms
        const startValue = parseInt(summaryTotal.innerText.replace(/[^0-9]/g, '')) || 0;
        const startTime = performance.now();

        if (totalAnimationTimer) cancelAnimationFrame(totalAnimationTimer);

        function updateCounter(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Ease out cubic
            const easeProgress = 1 - Math.pow(1 - progress, 3);
            const currentValue = Math.round(startValue + (targetValue - startValue) * easeProgress);

            summaryTotal.innerText = formatCurrency(currentValue);

            if (progress < 1) {
                totalAnimationTimer = requestAnimationFrame(updateCounter);
            }
        }

        totalAnimationTimer = requestAnimationFrame(updateCounter);
    }

    // Set up Estimator Listeners
    eventRadios.forEach(radio => radio.addEventListener('change', calculateEstimate));
    cateringRadios.forEach(radio => radio.addEventListener('change', calculateEstimate));
    guestSlider.addEventListener('input', calculateEstimate);
    
    // Guest capacity bubble visibility handlers
    guestSlider.addEventListener('mousedown', () => guestBubble.style.opacity = '1');
    guestSlider.addEventListener('touchstart', () => guestBubble.style.opacity = '1');
    guestSlider.addEventListener('mouseup', () => guestBubble.style.opacity = '0');
    guestSlider.addEventListener('touchend', () => guestBubble.style.opacity = '0');
    guestSlider.addEventListener('focus', () => guestBubble.style.opacity = '1');
    guestSlider.addEventListener('blur', () => guestBubble.style.opacity = '0');
    addonCheckboxes.forEach(box => box.addEventListener('change', calculateEstimate));

    // Run Initial Estimate
    calculateEstimate();

    // ==========================================
    // 5. TESTIMONIALS CAROUSEL
    // ==========================================
    const carouselTrack = document.getElementById('carousel-track');
    const carouselDots = document.querySelectorAll('.dot');
    let currentSlide = 0;
    const slideIntervalTime = 6000;
    let slideInterval;

    function moveCarousel(slideIndex) {
        currentSlide = slideIndex;
        carouselTrack.style.transform = `translateX(-${slideIndex * 100}%)`;
        carouselDots.forEach(dot => dot.classList.remove('active'));
        carouselDots[slideIndex].classList.add('active');
    }

    function autoPlaySlides() {
        slideInterval = setInterval(() => {
            let nextSlide = (currentSlide + 1) % carouselDots.length;
            moveCarousel(nextSlide);
        }, slideIntervalTime);
    }

    carouselDots.forEach(dot => {
        dot.addEventListener('click', () => {
            clearInterval(slideInterval);
            const index = parseInt(dot.getAttribute('data-slide'));
            moveCarousel(index);
            autoPlaySlides(); // restart autoplay
        });
    });

    // Initialize Autoplay
    autoPlaySlides();

    // ==========================================
    // 6. FAQS ACCORDION
    // ==========================================
    const faqHeaders = document.querySelectorAll('.faq-header');

    faqHeaders.forEach(header => {
        header.addEventListener('click', () => {
            const item = header.parentElement;
            const content = item.querySelector('.faq-content');

            // Close all other items
            document.querySelectorAll('.faq-item').forEach(otherItem => {
                if (otherItem !== item && otherItem.classList.contains('active')) {
                    otherItem.classList.remove('active');
                    otherItem.querySelector('.faq-content').style.maxHeight = '0';
                }
            });

            // Toggle active class
            item.classList.toggle('active');

            if (item.classList.contains('active')) {
                // Dynamically sets scrollHeight to trigger a smooth transition height
                content.style.maxHeight = `${content.scrollHeight}px`;
            } else {
                content.style.maxHeight = '0';
            }
        });
    });

    // ==========================================
    // 7. BOOKING INQUIRY MODAL (MULTI-STEP)
    // ==========================================
    const bookingModal = document.getElementById('booking-modal');
    const openBookingBtn = document.getElementById('btn-open-booking');
    const closeModalBtn = document.getElementById('close-modal-btn');
    const quickInquiryBtn = document.getElementById('btn-quick-inquiry');

    const bookingForm = document.getElementById('booking-form');
    const bookingModalBody = document.getElementById('booking-modal-body');

    // Navigation triggers
    const btnNext1 = document.getElementById('btn-next-1');
    const btnPrev2 = document.getElementById('btn-prev-2');
    const step1 = document.getElementById('step-1');
    const step2 = document.getElementById('step-2');
    const dot1 = document.querySelector('.step-dot[data-step="1"]');
    const dot2 = document.querySelector('.step-dot[data-step="2"]');
    const dot3 = document.querySelector('.step-dot[data-step="3"]');

    // Function to set tentative booking dates
    function initBookingFieldsFromPage() {
        const quickDateVal = document.getElementById('quick-date').value;
        const quickSessionVal = document.getElementById('quick-session').value;
        
        // Setup Date limits (min is tomorrow)
        const today = new Date();
        today.setDate(today.getDate() + 1);
        const minDateString = today.toISOString().split('T')[0];
        document.getElementById('booking-date').min = minDateString;
        document.getElementById('quick-date').min = minDateString;

        // Auto prepopulate booking date if chosen
        if (quickDateVal) {
            document.getElementById('booking-date').value = quickDateVal;
        } else {
            document.getElementById('booking-date').value = minDateString;
        }

        if (quickSessionVal) {
            document.getElementById('booking-session').value = quickSessionVal;
        }
    }

    function openModal() {
        initBookingFieldsFromPage();
        bookingModal.classList.add('active');
        document.body.style.overflow = 'hidden'; // Lock main scroll
    }

    function closeModal() {
        bookingModal.classList.remove('active');
        document.body.style.overflow = 'auto'; // Restore scroll
        resetBookingForm();
    }

    // Connect trigger buttons
    openBookingBtn.addEventListener('click', openModal);
    closeModalBtn.addEventListener('click', closeModal);
    
    // Quick Availability form submit -> Open modal prefilled
    quickInquiryBtn.addEventListener('click', () => {
        openModal();
    });

    // Close on overlay click
    bookingModal.addEventListener('click', (e) => {
        if (e.target === bookingModal) closeModal();
    });

    // Multi-step transitions
    btnNext1.addEventListener('click', () => {
        const dateInput = document.getElementById('booking-date');
        if (!dateInput.value) {
            dateInput.reportValidity();
            return;
        }
        
        // Animate swap
        step1.classList.remove('active');
        step2.classList.add('active');
        dot1.classList.add('completed');
        dot2.classList.add('active');
    });

    btnPrev2.addEventListener('click', () => {
        step2.classList.remove('active');
        step1.classList.add('active');
        dot1.classList.remove('completed');
        dot2.classList.remove('active');
    });

    // Submit Booking Form
    bookingForm.addEventListener('submit', (e) => {
        e.preventDefault();
        handleBookingSubmission(bookingForm, dot2, dot3, bookingModalBody, closeModal);
    });

    function handleBookingSubmission(formEl, d2, d3, modalBody, closeCallback) {
        const submitBtn = formEl.querySelector('button[type="submit"]') || document.getElementById('btn-submit-booking');
        const originalText = submitBtn.innerText;
        
        submitBtn.disabled = true;
        submitBtn.innerText = 'Locking in quotation...';

        const userName = document.getElementById('booking-name').value;
        const phone = document.getElementById('booking-phone').value;
        const email = document.getElementById('booking-email').value;
        const notes = document.getElementById('booking-notes').value;
        const bookingDate = document.getElementById('booking-date').value;
        const sessionVal = document.getElementById('booking-session').value;
        const sessionName = document.getElementById('booking-session').options[document.getElementById('booking-session').selectedIndex].text;
        const theme = document.getElementById('booking-theme').value;

        // Get Event Type from budget calculator page setting
        let eventType = 'wedding';
        document.querySelectorAll('input[name="estimator-event"]').forEach(radio => {
            if (radio.checked) eventType = radio.value;
        });

        const guests = document.getElementById('guest-slider').value;

        const addons = [];
        document.querySelectorAll('input[name="estimator-addon"]:checked').forEach(checkbox => {
            addons.push(checkbox.value);
        });

        const finalQuote = summaryTotal.innerText;
        const refNumber = `MANTRA-${Math.floor(100000 + Math.random() * 900000)}`;

        fetch('/api/bookings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: userName,
                phone: phone,
                email: email,
                notes: notes,
                date: bookingDate,
                session: sessionVal,
                theme: theme,
                event_type: eventType,
                guests: parseInt(guests),
                addons: addons,
                estimated_cost: finalQuote,
                ref_code: refNumber
            })
        })
        .then(res => {
            if (!res.ok) throw new Error('API submission failed');
            return res.json();
        })
        .then(data => {
            d2.classList.add('completed');
            d3.classList.add('active');

            modalBody.innerHTML = `
                <div class="booking-success-state">
                    <div class="success-badge">
                        <svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                    </div>
                    <h3>Reservation Quote Reserved!</h3>
                    <p>Congratulations <strong>${userName}</strong>, our reservation system has locked in your pricing configuration and saved it to the database. A dedicated hospitality consultant has been assigned to your reference.</p>
                    
                    <div class="booking-details-receipt">
                        <h4>Masala Mantra Reservation Receipt</h4>
                        <div class="receipt-row">
                            <span>Reference Code:</span>
                            <strong>${refNumber}</strong>
                        </div>
                        <div class="receipt-row">
                            <span>Event Date:</span>
                            <span>${bookingDate}</span>
                        </div>
                        <div class="receipt-row">
                            <span>Session / Duration:</span>
                            <span>${sessionName}</span>
                        </div>
                        <div class="receipt-row">
                            <span>Guest Load:</span>
                            <span>${guests} Guests</span>
                        </div>
                        <div class="receipt-row total">
                            <span>Lock-in Quotation:</span>
                            <span>${finalQuote}</span>
                        </div>
                    </div>
                    
                    <p style="font-size: 0.85rem; color: var(--text-muted-dark);">We have registered this request in our admin panel. Click close to return back to home details.</p>
                    <button type="button" class="btn-primary" id="btn-success-close" style="margin-top: 15px; width: 100%;">Close Confirmation</button>
                </div>
            `;
            document.getElementById('btn-success-close').addEventListener('click', closeCallback);
        })
        .catch(err => {
            console.error('Error submitting booking:', err);
            submitBtn.disabled = false;
            submitBtn.innerText = originalText;
            alert('Could not submit booking details. Please make sure the backend database server is running, or contact our support team.');
        });
    }

    function resetBookingForm() {
        setTimeout(() => {
            bookingModalBody.innerHTML = `
                <div class="steps-indicator">
                    <span class="step-dot active" data-step="1">1</span>
                    <span class="step-dot" data-step="2">2</span>
                    <span class="step-dot" data-step="3">3</span>
                </div>
                <form id="booking-form">
                    <div class="form-step active" id="step-1">
                        <h3>Reserve Celebration Space</h3>
                        <div class="form-row">
                            <div class="form-group">
                                <label for="booking-date">Celebration Date</label>
                                <input type="date" id="booking-date" required>
                            </div>
                            <div class="form-group">
                                <label for="booking-session">Time Session</label>
                                <select id="booking-session">
                                    <option value="morning">Morning (9 AM - 4 PM)</option>
                                    <option value="evening" selected>Evening (6 PM - Midnight)</option>
                                    <option value="fullday">Full Day Reservation</option>
                                </select>
                            </div>
                        </div>
                        <div class="form-group">
                            <label for="booking-theme">Aesthetic Visual Theme</label>
                            <select id="booking-theme">
                                <option value="gold-royal">Royal Imperial Gold & White Roses</option>
                                <option value="emerald-forest">Emerald Rustic Forest Garden</option>
                                <option value="modern-minimal">Minimalist Crystal Glass Elegance</option>
                                <option value="boho-sunset">Bohemian Sunset Glow Pastel</option>
                            </select>
                        </div>
                        <div class="step-buttons">
                            <div></div>
                            <button type="button" class="btn-primary" id="btn-next-1">Next Step</button>
                        </div>
                    </div>
                    <div class="form-step" id="step-2">
                        <h3>Contact Details</h3>
                        <div class="form-row">
                            <div class="form-group">
                                <label for="booking-name">Full Name</label>
                                <input type="text" id="booking-name" placeholder="John Doe" required>
                            </div>
                            <div class="form-group">
                                <label for="booking-phone">Mobile Number</label>
                                <input type="tel" id="booking-phone" placeholder="+91 99999 99999" required>
                            </div>
                        </div>
                        <div class="form-group">
                            <label for="booking-email">Email Address</label>
                            <input type="email" id="booking-email" placeholder="john@example.com" required>
                        </div>
                        <div class="form-group">
                            <label for="booking-notes">Special Dietary or Seating Notes</label>
                            <textarea id="booking-notes" rows="3" placeholder="Provide extra requirements like wheelchair ramp access, vegan food allergies, kids play zone etc..."></textarea>
                        </div>
                        <div class="step-buttons">
                            <button type="button" class="btn-outline" id="btn-prev-2">Previous</button>
                            <button type="submit" class="btn-primary" id="btn-submit-booking">Confirm Inquiry Details</button>
                        </div>
                    </div>
                </form>
            `;
            bindDynamicModalListeners();
        }, 500);
    }

    function bindDynamicModalListeners() {
        const dynamicForm = document.getElementById('booking-form');
        const next1 = document.getElementById('btn-next-1');
        const prev2 = document.getElementById('btn-prev-2');
        const step1 = document.getElementById('step-1');
        const step2 = document.getElementById('step-2');
        const d1 = document.querySelector('.step-dot[data-step="1"]');
        const d2 = document.querySelector('.step-dot[data-step="2"]');
        const d3 = document.querySelector('.step-dot[data-step="3"]');

        if (next1) {
            next1.addEventListener('click', () => {
                const dateVal = document.getElementById('booking-date');
                if (!dateVal.value) {
                    dateVal.reportValidity();
                    return;
                }
                step1.classList.remove('active');
                step2.classList.add('active');
                d1.classList.add('completed');
                d2.classList.add('active');
            });
        }

        if (prev2) {
            prev2.addEventListener('click', () => {
                step2.classList.remove('active');
                step1.classList.add('active');
                d1.classList.remove('completed');
                d2.classList.remove('active');
            });
        }

        if (dynamicForm) {
            dynamicForm.addEventListener('submit', (e) => {
                e.preventDefault();
                handleBookingSubmission(dynamicForm, d2, d3, bookingModalBody, closeModal);
            });
        }
    }

    // ==========================================
    // 8. CONTACT FORM SUBMISSION
    // ==========================================
    const contactForm = document.getElementById('contact-form');
    contactForm.addEventListener('submit', (e) => {
        e.preventDefault();
        
        const submitBtn = contactForm.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerText;
        submitBtn.disabled = true;
        submitBtn.innerText = 'Sending message...';

        const name = document.getElementById('contact-name').value;
        const phone = document.getElementById('contact-phone').value;
        const email = document.getElementById('contact-email').value;
        const notes = document.getElementById('contact-message').value;

        fetch('/api/inquiries', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, phone, email, notes })
        })
        .then(res => {
            if (!res.ok) throw new Error('API Error');
            return res.json();
        })
        .then(data => {
            contactForm.reset();
            submitBtn.disabled = false;
            submitBtn.innerText = originalText;
            showToast('Tour inquiry submitted! We will contact you soon.');
        })
        .catch(err => {
            console.error('Error submitting contact form:', err);
            submitBtn.disabled = false;
            submitBtn.innerText = originalText;
            alert('Failed to send tour inquiry. Please check if the server is running or contact us directly.');
        });
    });

    function showToast(message) {
        const toast = document.createElement('div');
        toast.style.position = 'fixed';
        toast.style.bottom = '20px';
        toast.style.right = '20px';
        toast.style.background = 'var(--gold-primary)';
        toast.style.color = 'var(--bg-dark)';
        toast.style.padding = '15px 30px';
        toast.style.borderRadius = '30px';
        toast.style.fontWeight = '700';
        toast.style.boxShadow = 'var(--shadow-lg)';
        toast.style.zIndex = '2000';
        toast.innerText = message;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transition = 'opacity 0.6s ease';
            setTimeout(() => toast.remove(), 600);
        }, 3000);
    }

});
